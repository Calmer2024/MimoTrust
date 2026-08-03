import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:just_audio/just_audio.dart';

import '../models/content_context.dart';
import '../models/sandbox_comment.dart';
import '../models/sandbox_content.dart';
import '../services/content_grant_client.dart';
import '../services/context_dispatcher.dart';
import '../services/context_transport.dart';
import '../services/local_interaction_store.dart';
import '../widgets/comments_sheet.dart';
import '../widgets/share_sheet.dart';

class NonVideoContentPage extends StatefulWidget {
  const NonVideoContentPage({
    super.key,
    required this.content,
    required this.isActive,
    this.isDetail = false,
    this.initialReadingOffset = 0,
    this.initialGalleryIndex = 0,
    this.onReadingOffsetChanged,
    this.onGalleryIndexChanged,
    this.interactionStore = const SharedPreferencesInteractionStore(),
    this.contextDispatcher,
    this.httpClient,
  });

  final SandboxContent content;
  final bool isActive;
  final bool isDetail;
  final double initialReadingOffset;
  final int initialGalleryIndex;
  final ValueChanged<double>? onReadingOffsetChanged;
  final ValueChanged<int>? onGalleryIndexChanged;
  final InteractionStore interactionStore;
  final ContextDispatcher? contextDispatcher;
  final http.Client? httpClient;

  @override
  State<NonVideoContentPage> createState() => _NonVideoContentPageState();
}

class _NonVideoContentPageState extends State<NonVideoContentPage>
    with WidgetsBindingObserver {
  late final ScrollController _readingController;
  late final PageController _galleryController;
  late final List<GlobalKey> _richBlockKeys;
  late final ContextDispatcher _contextDispatcher;
  late final bool _ownsContextDispatcher;
  late final GuardianContextRequestHandler _guardianRequestHandler;
  late final http.Client _httpClient;
  late final bool _ownsHttpClient;
  AudioPlayer? _audioPlayer;
  StreamSubscription<PlayerState>? _playerStateSubscription;
  StreamSubscription<Duration>? _positionSubscription;
  StreamSubscription<Duration?>? _durationSubscription;
  String? _articleBody;
  Object? _articleError;
  bool _liked = false;
  List<SandboxComment> _localComments = const <SandboxComment>[];
  int _sessionShareCount = 0;
  int _activeAssetIndex = 0;
  int _visibleBlockIndex = 0;
  double _readingProgress = 0;
  bool _galleryZoomed = false;
  bool _readingOffsetRestored = false;
  Duration _audioPosition = Duration.zero;
  Duration? _audioDuration;
  bool _audioLoading = false;
  Object? _audioError;

  static const _presetComments = <SandboxComment>[
    SandboxComment(author: '访客 01', body: '建议核对原始来源与发布时间。'),
    SandboxComment(author: '访客 02', body: '这里的关键信息还需要更多证据。'),
  ];

  @override
  void initState() {
    super.initState();
    final galleryCount = widget.content is ImageGalleryContent
        ? (widget.content as ImageGalleryContent).images.length
        : 1;
    _activeAssetIndex = widget.initialGalleryIndex.clamp(0, galleryCount - 1);
    _readingController = ScrollController()..addListener(_onReadingChanged);
    _galleryController = PageController(initialPage: _activeAssetIndex);
    _richBlockKeys = widget.content is RichArticleContent
        ? List<GlobalKey>.generate(
            (widget.content as RichArticleContent).blocks.length,
            (index) => GlobalKey(debugLabel: 'rich-block-$index'),
          )
        : const <GlobalKey>[];
    _ownsContextDispatcher = widget.contextDispatcher == null;
    _contextDispatcher =
        widget.contextDispatcher ??
        ContextDispatcher(
          GatewayContentGrantClient(
            baseUrl: Uri.parse(
              const String.fromEnvironment(
                'MIMOTRUST_GATEWAY_URL',
                defaultValue: 'http://127.0.0.1:8787',
              ),
            ),
          ),
        );
    _guardianRequestHandler = _handleGuardianRequest;
    _ownsHttpClient = widget.httpClient == null;
    _httpClient = widget.httpClient ?? http.Client();
    WidgetsBinding.instance.addObserver(this);
    if (widget.isActive) {
      GuardianRequestBridge.activate(_guardianRequestHandler);
    }
    unawaited(_loadInteractions());
    if (widget.content case final ArticleContent article) {
      unawaited(_loadArticle(article));
    } else if (widget.content is RichArticleContent) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _restoreReadingOffset();
      });
    }
    if (widget.content case final AudioContent audio) {
      unawaited(_initializeAudio(audio));
    }
  }

  @override
  void didUpdateWidget(covariant NonVideoContentPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.isActive != widget.isActive) {
      if (widget.isActive) {
        GuardianRequestBridge.activate(_guardianRequestHandler);
      } else {
        GuardianRequestBridge.deactivate(_guardianRequestHandler);
      }
    }
    if (widget.content is AudioContent && oldWidget.isActive != widget.isActive) {
      unawaited(_syncAudioActiveState());
    }
  }

  Future<void> _loadInteractions() async {
    try {
      final liked = await widget.interactionStore.loadLiked(
        widget.content.id,
        widget.content.version,
      );
      final comments = await widget.interactionStore.loadComments(
        widget.content.id,
        widget.content.version,
      );
      if (mounted) {
        setState(() {
          _liked = liked;
          _localComments = comments;
        });
      }
    } catch (_) {
      // Local state is optional and never blocks content rendering.
    }
  }

  void _onReadingChanged() {
    if (!_readingController.hasClients) return;
    final maxExtent = _readingController.position.maxScrollExtent;
    final progress = maxExtent <= 0
        ? 0.0
        : (_readingController.offset / maxExtent).clamp(0.0, 1.0);
    final visibleBlock = _findVisibleRichBlock();
    widget.onReadingOffsetChanged?.call(_readingController.offset);
    if (mounted &&
        ((progress - _readingProgress).abs() > 0.002 ||
            visibleBlock != _visibleBlockIndex)) {
      setState(() {
        _readingProgress = progress;
        _visibleBlockIndex = visibleBlock;
      });
    }
  }

  void _restoreReadingOffset() {
    if (_readingOffsetRestored ||
        !mounted ||
        !_readingController.hasClients) {
      return;
    }
    final target = widget.initialReadingOffset.clamp(
      0.0,
      _readingController.position.maxScrollExtent,
    );
    _readingOffsetRestored = true;
    if (target > 0) _readingController.jumpTo(target);
  }

  int _findVisibleRichBlock() {
    if (widget.content is! RichArticleContent || _richBlockKeys.isEmpty) {
      return 0;
    }
    final anchor = MediaQuery.paddingOf(context).top + 74;
    var result = _visibleBlockIndex;
    var closestDistance = double.infinity;
    for (var index = 0; index < _richBlockKeys.length; index += 1) {
      final blockContext = _richBlockKeys[index].currentContext;
      final renderObject = blockContext?.findRenderObject();
      if (renderObject is! RenderBox || !renderObject.attached) continue;
      final top = renderObject.localToGlobal(Offset.zero).dy;
      final bottom = top + renderObject.size.height;
      if (bottom < anchor) continue;
      final distance = (top - anchor).abs();
      if (distance < closestDistance) {
        closestDistance = distance;
        result = index;
      }
    }
    return result;
  }

  Future<void> _loadArticle(ArticleContent content) async {
    if (mounted) {
      setState(() {
        _articleBody = null;
        _articleError = null;
      });
    }
    try {
      final response = await _httpClient.get(content.bodyUrl).timeout(
        const Duration(seconds: 8),
      );
      if (response.statusCode != 200) {
        throw StateError('HTTP ${response.statusCode}');
      }
      final body = utf8.decode(response.bodyBytes);
      if (mounted) {
        setState(() => _articleBody = body);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          _restoreReadingOffset();
        });
      }
    } catch (error) {
      if (mounted) setState(() => _articleError = error);
    }
  }

  Future<void> _initializeAudio(AudioContent content) async {
    final player = AudioPlayer();
    _audioPlayer = player;
    _playerStateSubscription = player.playerStateStream.listen((_) {
      if (mounted) setState(() {});
    });
    _positionSubscription = player.positionStream.listen((position) {
      if (mounted) setState(() => _audioPosition = position);
    });
    _durationSubscription = player.durationStream.listen((duration) {
      if (mounted) setState(() => _audioDuration = duration);
    });
    setState(() {
      _audioLoading = true;
      _audioError = null;
    });
    try {
      await player.setUrl(content.audioUrl.toString());
      if (widget.isActive) await player.play();
    } catch (error) {
      if (mounted) setState(() => _audioError = error);
    } finally {
      if (mounted) setState(() => _audioLoading = false);
    }
  }

  Future<void> _syncAudioActiveState() async {
    final player = _audioPlayer;
    if (player == null) return;
    if (widget.isActive &&
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed) {
      await player.play();
    } else {
      await player.pause();
    }
  }

  Future<void> _toggleLiked() async {
    final value = !_liked;
    setState(() => _liked = value);
    try {
      await widget.interactionStore.setLiked(
        widget.content.id,
        widget.content.version,
        value,
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('点赞状态暂时无法保存')),
        );
      }
    }
  }

  Future<void> _addComment(SandboxComment comment) async {
    setState(() {
      _localComments = <SandboxComment>[..._localComments, comment];
    });
    try {
      await widget.interactionStore.addComment(
        widget.content.id,
        widget.content.version,
        comment,
      );
    } catch (_) {
      // The in-memory comment remains visible for this session.
    }
  }

  Future<void> _openComments() async {
    _requestContext(ContextTrigger.comment);
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: const Color(0xFF161616),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(8)),
      ),
      builder: (context) => CommentsSheet(
        presetComments: _presetComments,
        localComments: _localComments,
        baseCount: widget.content.displayMetrics.commentCount,
        onCommentAdded: _addComment,
      ),
    );
  }

  Future<void> _openShare() async {
    _requestContext(ContextTrigger.share);
    final contact = await showModalBottomSheet<SandboxContact>(
      context: context,
      useSafeArea: true,
      backgroundColor: const Color(0xFF161616),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(8)),
      ),
      builder: (context) => const ShareSheet(),
    );
    if (mounted && contact != null) {
      setState(() => _sessionShareCount += 1);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('已模拟转发给 ${contact.name}')),
      );
    }
  }

  void _requestContext(ContextTrigger trigger) {
    unawaited(_dispatchContext(trigger, _currentViewState()));
  }

  ContentViewState _currentViewState() {
    final content = widget.content;
    if (content case final AudioContent audio) {
      final duration = _audioDuration ?? audio.duration;
      final durationMs = duration.inMilliseconds.clamp(1, 1 << 31);
      return MediaViewState(
        positionMs: _audioPosition.inMilliseconds.clamp(0, durationMs),
        durationMs: durationMs,
        isPlaying: _audioPlayer?.playing ?? false,
      );
    }
    if (content case final ImageGalleryContent gallery) {
      return GalleryViewState(
        activeAssetIndex: _activeAssetIndex,
        assetCount: gallery.images.length,
      );
    }
    final maxExtent = _readingController.hasClients
        ? _readingController.position.maxScrollExtent
        : 0.0;
    final ratio = maxExtent <= 0
        ? 0.0
        : (_readingController.offset / maxExtent).clamp(0.0, 1.0);
    return ReadingViewState(
      scrollRatio: ratio,
      blockIndex: content is RichArticleContent ? _visibleBlockIndex : 0,
    );
  }

  Future<void> _dispatchContext(
    ContextTrigger trigger,
    ContentViewState viewState,
  ) async {
    try {
      await _contextDispatcher.dispatchContext(
        trigger: trigger,
        content: widget.content,
        viewState: viewState,
      );
    } catch (error) {
      debugPrint(
        'CONTEXT_DISPATCH_FAILED trigger=${trigger.wireValue} '
        'error=${error.runtimeType}',
      );
    }
  }

  Future<void> _handleGuardianRequest(String requestId) async {
    if (!mounted ||
        !widget.isActive ||
        WidgetsBinding.instance.lifecycleState != AppLifecycleState.resumed) {
      throw StateError('No foreground active content.');
    }
    await _contextDispatcher.dispatchGuardianRequest(
      requestId: requestId,
      content: widget.content,
      viewState: _currentViewState(),
      observedAt: DateTime.now().toUtc(),
    );
  }

  Future<void> _openImage(Uri imageUrl) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (context) => FullScreenImagePage(imageUrl: imageUrl),
      ),
    );
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      GuardianRequestBridge.deactivate(_guardianRequestHandler);
    } else if (state == AppLifecycleState.resumed && widget.isActive) {
      GuardianRequestBridge.activate(_guardianRequestHandler);
    }
    final player = _audioPlayer;
    if (player == null) return;
    if (state != AppLifecycleState.resumed) {
      unawaited(player.pause());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    GuardianRequestBridge.deactivate(_guardianRequestHandler);
    if (_readingController.hasClients) {
      widget.onReadingOffsetChanged?.call(_readingController.offset);
    }
    widget.onGalleryIndexChanged?.call(_activeAssetIndex);
    _readingController.removeListener(_onReadingChanged);
    _readingController.dispose();
    _galleryController.dispose();
    unawaited(_playerStateSubscription?.cancel());
    unawaited(_positionSubscription?.cancel());
    unawaited(_durationSubscription?.cancel());
    unawaited(_audioPlayer?.dispose());
    if (_ownsContextDispatcher) _contextDispatcher.close();
    if (_ownsHttpClient) _httpClient.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF6F7F8),
      body: Stack(
        fit: StackFit.expand,
        children: [
          Positioned.fill(child: _contentBody()),
          _ContentHeader(
            showBack: widget.isDetail,
            readingProgress:
                widget.content is ArticleContent ||
                    widget.content is RichArticleContent
                ? _readingProgress
                : null,
          ),
          if (widget.isDetail)
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: _BottomContentActions(
                liked: _liked,
                likeCount:
                    widget.content.displayMetrics.likeCount + (_liked ? 1 : 0),
                commentCount:
                    widget.content.displayMetrics.commentCount +
                    _localComments.length,
                shareCount:
                    widget.content.displayMetrics.shareCount +
                    _sessionShareCount,
                onLike: _toggleLiked,
                onComment: _openComments,
                onShare: _openShare,
              ),
            )
          else
            Positioned(
              right: 8,
              bottom: 30,
              child: _ContentActions(
              liked: _liked,
              likeCount:
                  widget.content.displayMetrics.likeCount + (_liked ? 1 : 0),
              commentCount:
                  widget.content.displayMetrics.commentCount +
                  _localComments.length,
              shareCount:
                  widget.content.displayMetrics.shareCount +
                  _sessionShareCount,
              onLike: _toggleLiked,
              onComment: _openComments,
              onShare: _openShare,
            ),
            ),
        ],
      ),
    );
  }

  Widget _contentBody() {
    return switch (widget.content) {
      final ArticleContent content => _article(content),
      final RichArticleContent content => _richArticle(content),
      final ImageGalleryContent content => _gallery(content),
      final AudioContent content => _audio(content),
      _ => const Center(child: Text('不支持的内容类型')),
    };
  }

  Widget _article(ArticleContent content) {
    return SafeArea(
      child: ListView(
        key: const Key('article-scroll'),
        controller: _readingController,
        padding: EdgeInsets.fromLTRB(
          22,
          76,
          widget.isDetail ? 22 : 68,
          widget.isDetail ? 118 : 48,
        ),
        children: [
          _ArticleHeading(content: content),
          const SizedBox(height: 26),
          if (_articleBody != null)
            ..._articleParagraphs(_articleBody!).map(
              (paragraph) => Padding(
                padding: const EdgeInsets.only(bottom: 18),
                child: Text(
                  paragraph,
                  style: const TextStyle(
                    color: Color(0xFF24272B),
                    fontSize: 17,
                    height: 1.85,
                  ),
                ),
              ),
            )
          else if (_articleError != null)
            _InlineError(onRetry: () => _loadArticle(content))
          else
            const Center(child: CircularProgressIndicator()),
        ],
      ),
    );
  }

  Widget _richArticle(RichArticleContent content) {
    return SafeArea(
      child: ListView.builder(
        key: const Key('rich-article-scroll'),
        controller: _readingController,
        padding: EdgeInsets.fromLTRB(
          22,
          76,
          widget.isDetail ? 22 : 68,
          widget.isDetail ? 118 : 48,
        ),
        itemCount: content.blocks.length + 1,
        itemBuilder: (context, index) {
          if (index == 0) return _ArticleHeading(content: content);
          final block = content.blocks[index - 1];
          return Padding(
            key: _richBlockKeys[index - 1],
            padding: const EdgeInsets.only(top: 20),
            child: block.type == 'text'
                ? Text(
                    block.text!,
                    style: const TextStyle(
                      color: Color(0xFF24272B),
                      fontSize: 17,
                      height: 1.8,
                    ),
                  )
                : GestureDetector(
                    onTap: () => _openImage(block.asset!.sourceUrl),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: Image.network(
                        block.asset!.sourceUrl.toString(),
                        fit: BoxFit.fitWidth,
                        errorBuilder: _imageError,
                      ),
                    ),
                  ),
          );
        },
      ),
    );
  }

  Widget _gallery(ImageGalleryContent content) {
    return ColoredBox(
      color: Colors.black,
      child: Stack(
        children: [
          PageView.builder(
            key: const Key('gallery-pages'),
            controller: _galleryController,
            physics: _galleryZoomed
                ? const NeverScrollableScrollPhysics()
                : const PageScrollPhysics(),
            itemCount: content.images.length,
            onPageChanged: (index) {
              setState(() {
                _activeAssetIndex = index;
                _galleryZoomed = false;
              });
              widget.onGalleryIndexChanged?.call(index);
            },
            itemBuilder: (context, index) => _ZoomableNetworkImage(
              key: ValueKey(content.images[index].id),
              imageUrl: content.images[index].sourceUrl,
              onZoomChanged: index == _activeAssetIndex
                  ? (zoomed) {
                      if (mounted && zoomed != _galleryZoomed) {
                        setState(() => _galleryZoomed = zoomed);
                      }
                    }
                  : null,
            ),
          ),
          Positioned(
            left: 18,
            right: widget.isDetail ? 18 : 68,
            bottom: widget.isDetail ? 100 : 28,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  content.title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '${_activeAssetIndex + 1} / ${content.images.length}  ·  ${content.author}',
                  style: const TextStyle(color: Color(0xFFD7DADF)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _audio(AudioContent content) {
    final duration = _audioDuration ?? content.duration;
    final maxMs = duration.inMilliseconds.clamp(1, 1 << 31);
    final positionMs = _audioPosition.inMilliseconds.clamp(0, maxMs);
    final playing = _audioPlayer?.playing ?? false;
    return ColoredBox(
      color: const Color(0xFF151719),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(30, 92, 70, 42),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              AspectRatio(
                aspectRatio: 1,
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(6),
                  child: content.coverUrl == null
                      ? const ColoredBox(
                          color: Color(0xFF2A2E32),
                          child: Icon(
                            Icons.graphic_eq_rounded,
                            color: Colors.white70,
                            size: 72,
                          ),
                        )
                      : Image.network(
                          content.coverUrl.toString(),
                          fit: BoxFit.cover,
                          errorBuilder: _imageError,
                        ),
                ),
              ),
              const SizedBox(height: 26),
              Text(
                content.title,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 21,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              Text(content.author, style: const TextStyle(color: Colors.white60)),
              const SizedBox(height: 20),
              Slider(
                value: positionMs.toDouble(),
                max: maxMs.toDouble(),
                onChanged: _audioError == null
                    ? (value) => _audioPlayer?.seek(
                        Duration(milliseconds: value.round()),
                      )
                    : null,
              ),
              if (_audioLoading)
                const CircularProgressIndicator()
              else if (_audioError != null)
                FilledButton.icon(
                  onPressed: () => _initializeAudio(content),
                  icon: const Icon(Icons.refresh),
                  label: const Text('重新加载音频'),
                )
              else
                IconButton.filled(
                  tooltip: playing ? '暂停' : '播放',
                  iconSize: 34,
                  onPressed: () => playing
                      ? _audioPlayer?.pause()
                      : _audioPlayer?.play(),
                  icon: Icon(
                    playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  static Widget _imageError(
    BuildContext context,
    Object error,
    StackTrace? stackTrace,
  ) {
    return const ColoredBox(
      color: Color(0xFF272A2E),
      child: Center(
        child: Icon(Icons.broken_image_outlined, color: Colors.white54, size: 42),
      ),
    );
  }

  static List<String> _articleParagraphs(String body) {
    return body
        .split(RegExp(r'\r?\n\s*\r?\n'))
        .map((paragraph) => paragraph.trim())
        .where((paragraph) => paragraph.isNotEmpty)
        .toList(growable: false);
  }
}

class _ContentHeader extends StatelessWidget {
  const _ContentHeader({required this.showBack, this.readingProgress});

  final bool showBack;
  final double? readingProgress;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 6, 10, 0),
            child: Row(
              children: [
                if (showBack)
                  IconButton.filledTonal(
                    key: const Key('content-detail-back'),
                    tooltip: '返回',
                    onPressed: () => Navigator.of(context).maybePop(),
                    icon: const Icon(Icons.arrow_back_rounded),
                  ),
                if (showBack) const SizedBox(width: 8),
                DecoratedBox(
                  decoration: BoxDecoration(
                    color: const Color(0xE6111111),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                    child: Text(
                      'MiMoTrust  ·  受控内容',
                      style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (readingProgress != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: LinearProgressIndicator(
                key: const Key('reading-progress'),
                value: readingProgress,
                minHeight: 2,
                backgroundColor: Colors.transparent,
              ),
            ),
        ],
      ),
    );
  }
}

class FullScreenImagePage extends StatelessWidget {
  const FullScreenImagePage({super.key, required this.imageUrl});

  final Uri imageUrl;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          _ZoomableNetworkImage(imageUrl: imageUrl),
          SafeArea(
            child: Align(
              alignment: Alignment.topLeft,
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: IconButton.filledTonal(
                  tooltip: '返回',
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.arrow_back_rounded),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ZoomableNetworkImage extends StatefulWidget {
  const _ZoomableNetworkImage({
    super.key,
    required this.imageUrl,
    this.onZoomChanged,
  });

  final Uri imageUrl;
  final ValueChanged<bool>? onZoomChanged;

  @override
  State<_ZoomableNetworkImage> createState() => _ZoomableNetworkImageState();
}

class _ZoomableNetworkImageState extends State<_ZoomableNetworkImage> {
  final TransformationController _controller = TransformationController();
  bool _zoomed = false;

  void _updateZoomState() {
    final zoomed = _controller.value.getMaxScaleOnAxis() > 1.01;
    if (zoomed == _zoomed) return;
    setState(() => _zoomed = zoomed);
    widget.onZoomChanged?.call(zoomed);
  }

  void _toggleZoom() {
    _controller.value = _zoomed
        ? Matrix4.identity()
        : Matrix4.diagonal3Values(2.5, 2.5, 1);
    _updateZoomState();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onDoubleTap: _toggleZoom,
      child: InteractiveViewer(
        transformationController: _controller,
        minScale: 1,
        maxScale: 4,
        panEnabled: _zoomed,
        onInteractionUpdate: (_) => _updateZoomState(),
        onInteractionEnd: (_) => _updateZoomState(),
        child: Center(
          child: Image.network(
            widget.imageUrl.toString(),
            fit: BoxFit.contain,
            errorBuilder: _NonVideoContentPageState._imageError,
          ),
        ),
      ),
    );
  }
}

class _ArticleHeading extends StatelessWidget {
  const _ArticleHeading({required this.content});

  final SandboxContent content;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          content.title,
          style: const TextStyle(
            color: Color(0xFF16181B),
            fontSize: 27,
            height: 1.35,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 14),
        Text(
          '${content.author}  ·  ${content.publishedAt.substring(0, 10)}',
          style: const TextStyle(color: Color(0xFF6A7077), fontSize: 14),
        ),
      ],
    );
  }
}

class _InlineError extends StatelessWidget {
  const _InlineError({required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.cloud_off_outlined, color: Color(0xFF555B62), size: 42),
          const SizedBox(height: 12),
          const Text('正文暂时无法加载', style: TextStyle(color: Color(0xFF30343A))),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('重试'),
          ),
        ],
      ),
    );
  }
}

class _BottomContentActions extends StatelessWidget {
  const _BottomContentActions({
    required this.liked,
    required this.likeCount,
    required this.commentCount,
    required this.shareCount,
    required this.onLike,
    required this.onComment,
    required this.onShare,
  });

  final bool liked;
  final int likeCount;
  final int commentCount;
  final int shareCount;
  final VoidCallback onLike;
  final VoidCallback onComment;
  final VoidCallback onShare;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: const Color(0xF2121416),
      child: SafeArea(
        top: false,
        minimum: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        child: SizedBox(
          height: 58,
          child: Row(
            children: [
              _BottomAction(
                key: const Key('action-like'),
                icon: liked ? Icons.favorite : Icons.favorite_border,
                color: liked ? const Color(0xFFFF5A5F) : Colors.white,
                label: _compactCount(likeCount),
                tooltip: liked ? '取消点赞' : '点赞',
                onPressed: onLike,
              ),
              _BottomAction(
                key: const Key('action-comment'),
                icon: Icons.chat_bubble_outline,
                label: _compactCount(commentCount),
                tooltip: '评论',
                onPressed: onComment,
              ),
              _BottomAction(
                key: const Key('action-share'),
                icon: Icons.reply_rounded,
                label: _compactCount(shareCount),
                tooltip: '转发',
                onPressed: onShare,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _BottomAction extends StatelessWidget {
  const _BottomAction({
    super.key,
    required this.icon,
    required this.label,
    required this.tooltip,
    required this.onPressed,
    this.color = Colors.white,
  });

  final IconData icon;
  final String label;
  final String tooltip;
  final VoidCallback onPressed;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Tooltip(
        message: tooltip,
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(4),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: color, size: 24),
              const SizedBox(width: 7),
              Text(label, style: const TextStyle(color: Colors.white)),
            ],
          ),
        ),
      ),
    );
  }
}

class _ContentActions extends StatelessWidget {
  const _ContentActions({
    required this.liked,
    required this.likeCount,
    required this.commentCount,
    required this.shareCount,
    required this.onLike,
    required this.onComment,
    required this.onShare,
  });

  final bool liked;
  final int likeCount;
  final int commentCount;
  final int shareCount;
  final VoidCallback onLike;
  final VoidCallback onComment;
  final VoidCallback onShare;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: const Color(0xD9111111),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _ActionButton(
              key: const Key('action-like'),
              icon: liked ? Icons.favorite : Icons.favorite_border,
              color: liked ? const Color(0xFFFF5A5F) : Colors.white,
              label: _compactCount(likeCount),
              tooltip: liked ? '取消点赞' : '点赞',
              onPressed: onLike,
            ),
            _ActionButton(
              key: const Key('action-comment'),
              icon: Icons.chat_bubble_outline,
              label: _compactCount(commentCount),
              tooltip: '评论',
              onPressed: onComment,
            ),
            _ActionButton(
              key: const Key('action-share'),
              icon: Icons.reply_rounded,
              label: _compactCount(shareCount),
              tooltip: '转发',
              onPressed: onShare,
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    super.key,
    required this.icon,
    required this.label,
    required this.tooltip,
    required this.onPressed,
    this.color = Colors.white,
  });

  final IconData icon;
  final String label;
  final String tooltip;
  final VoidCallback onPressed;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 50,
      height: 62,
      child: Column(
        children: [
          IconButton(
            tooltip: tooltip,
            visualDensity: VisualDensity.compact,
            onPressed: onPressed,
            color: color,
            icon: Icon(icon),
          ),
          Text(label, style: const TextStyle(color: Colors.white, fontSize: 11)),
        ],
      ),
    );
  }
}

String _compactCount(int value) {
  if (value >= 10000) return '${(value / 10000).toStringAsFixed(1)}万';
  return value.toString();
}
