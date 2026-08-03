import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:video_player/video_player.dart';

import '../models/content_context.dart';
import '../models/sandbox_comment.dart';
import '../models/sandbox_content.dart';
import '../models/video_content.dart';
import '../services/content_grant_client.dart';
import '../services/context_dispatcher.dart';
import '../services/context_transport.dart';
import '../services/local_interaction_store.dart';
import '../services/playback_lifecycle_policy.dart';
import '../widgets/comments_sheet.dart';
import '../widgets/share_sheet.dart';
import 'content_preview_page.dart';
import 'non_video_content_page.dart';

typedef VideoPageBuilder = Widget Function(VideoContent content);

class VideoContentPage extends StatefulWidget {
  const VideoContentPage({
    super.key,
    required this.loadContents,
    this.videoBuilder,
  });

  final Future<List<SandboxContent>> Function() loadContents;
  final VideoPageBuilder? videoBuilder;

  @override
  State<VideoContentPage> createState() => _VideoContentPageState();
}

class _VideoContentPageState extends State<VideoContentPage>
    with WidgetsBindingObserver {
  late Future<List<SandboxContent>> _contents;
  final PageController _feedController = PageController();
  final Map<String, double> _readingOffsets = <String, double>{};
  final Map<String, int> _galleryIndexes = <String, int>{};
  int _activeIndex = 0;
  bool _wasBackgrounded = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _contents = widget.loadContents();
  }

  void _retry() {
    setState(() {
      _contents = widget.loadContents();
    });
  }

  void _restoreActivePage(int itemCount) {
    final target = _activeIndex.clamp(0, itemCount - 1);
    _activeIndex = target;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_feedController.hasClients) return;
      final current = _feedController.page?.round();
      if (current != target) _feedController.jumpToPage(target);
    });
  }

  Future<void> _openDetails(SandboxContent content) async {
    final contentKey = '${content.id}:${content.version}';
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (context) => NonVideoContentPage(
          content: content,
          isActive: true,
          isDetail: true,
          initialReadingOffset: _readingOffsets[contentKey] ?? 0,
          initialGalleryIndex: _galleryIndexes[contentKey] ?? 0,
          onReadingOffsetChanged: (offset) {
            _readingOffsets[contentKey] = offset;
          },
          onGalleryIndexChanged: (index) {
            _galleryIndexes[contentKey] = index;
          },
        ),
      ),
    );
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      _wasBackgrounded = true;
    } else if (state == AppLifecycleState.resumed && _wasBackgrounded) {
      _wasBackgrounded = false;
      _retry();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _feedController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(
        statusBarColor: Colors.transparent,
        systemNavigationBarColor: Colors.black,
      ),
      child: FutureBuilder<List<SandboxContent>>(
        future: _contents,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const _ContentStatusView.loading();
          }
          if (snapshot.hasError || !snapshot.hasData || snapshot.data!.isEmpty) {
            return _ContentStatusView.error(onRetry: _retry);
          }
          final contents = snapshot.requireData;
          _restoreActivePage(contents.length);
          return Stack(
            children: [
              PageView.builder(
                key: const Key('video-feed'),
                controller: _feedController,
                scrollDirection: Axis.vertical,
                itemCount: contents.length,
                onPageChanged: (index) {
                  setState(() {
                    _activeIndex = index;
                  });
                },
                itemBuilder: (context, index) {
                  final content = contents[index];
                  if (content is VideoContent) {
                    return widget.videoBuilder?.call(content) ??
                        NetworkVideoPage(
                          key: ValueKey('${content.id}:${content.version}'),
                          content: content,
                          isActive: index == _activeIndex,
                        );
                  }
                  if (content is AudioContent) {
                    return NonVideoContentPage(
                      key: ValueKey('${content.id}:${content.version}'),
                      content: content,
                      isActive: index == _activeIndex,
                    );
                  }
                  return ContentPreviewPage(
                    key: ValueKey('${content.id}:${content.version}'),
                    content: content,
                    isActive: index == _activeIndex,
                    onOpen: () => _openDetails(content),
                  );
                },
              ),
              SafeArea(
                child: Align(
                  alignment: Alignment.topRight,
                  child: Padding(
                    padding: const EdgeInsets.only(top: 6, right: 10),
                    child: IconButton.filledTonal(
                      key: const Key('refresh-feed'),
                      tooltip: '刷新内容',
                      onPressed: _retry,
                      icon: const Icon(Icons.refresh_rounded),
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class NetworkVideoPage extends StatefulWidget {
  const NetworkVideoPage({
    super.key,
    required this.content,
    this.isActive = true,
    this.interactionStore = const SharedPreferencesInteractionStore(),
    this.contextDispatcher,
  });

  final VideoContent content;
  final bool isActive;
  final InteractionStore interactionStore;
  final ContextDispatcher? contextDispatcher;

  @override
  State<NetworkVideoPage> createState() => _NetworkVideoPageState();
}

class _NetworkVideoPageState extends State<NetworkVideoPage>
    with WidgetsBindingObserver {
  VideoPlayerController? _controller;
  Object? _loadError;
  bool _loading = true;
  bool _muted = false;
  bool _liked = false;
  List<SandboxComment> _localComments = const <SandboxComment>[];
  int _sessionShareCount = 0;
  final PlaybackLifecyclePolicy _playbackLifecycle = PlaybackLifecyclePolicy();
  late final ContextDispatcher _contextDispatcher;
  late final bool _ownsContextDispatcher;
  late final GuardianContextRequestHandler _guardianRequestHandler;

  static const _presetComments = <SandboxComment>[
    SandboxComment(author: '访客 01', body: '这个说法有可靠的原始来源吗？'),
    SandboxComment(author: '访客 02', body: '视频里的搜索截图需要核对时间和出处。'),
    SandboxComment(author: '访客 03', body: '先看原始发布信息，不要只看二次转述。'),
  ];

  @override
  void initState() {
    super.initState();
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
    WidgetsBinding.instance.addObserver(this);
    if (widget.isActive) {
      GuardianRequestBridge.activate(_guardianRequestHandler);
    }
    unawaited(_initialize());
    unawaited(_loadInteractions());
  }

  @override
  void didUpdateWidget(covariant NetworkVideoPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.content.videoUrl != widget.content.videoUrl) {
      unawaited(_initialize());
    }
    if (oldWidget.isActive != widget.isActive) {
      if (widget.isActive) {
        GuardianRequestBridge.activate(_guardianRequestHandler);
      } else {
        GuardianRequestBridge.deactivate(_guardianRequestHandler);
      }
      unawaited(_syncActiveState());
    }
    if (oldWidget.content.id != widget.content.id ||
        oldWidget.content.version != widget.content.version) {
      _sessionShareCount = 0;
      unawaited(_loadInteractions());
    }
  }

  Future<void> _loadInteractions() async {
    var liked = false;
    var comments = const <SandboxComment>[];
    try {
      liked = await widget.interactionStore.loadLiked(
        widget.content.id,
        widget.content.version,
      );
    } catch (_) {
      // Local interaction failures must not block content playback.
    }
    try {
      comments = await widget.interactionStore.loadComments(
        widget.content.id,
        widget.content.version,
      );
    } catch (_) {
      // The sheet remains usable with only the preset comments.
    }
    if (mounted) {
      setState(() {
        _liked = liked;
        _localComments = comments;
      });
    }
  }

  Future<void> _initialize() async {
    _playbackLifecycle.clear();
    final previous = _controller;
    if (previous != null) {
      previous.removeListener(_onVideoChanged);
      await previous.dispose();
    }
    if (mounted) {
      setState(() {
        _controller = null;
        _loadError = null;
        _loading = true;
      });
    }

    final controller = VideoPlayerController.networkUrl(
      widget.content.videoUrl,
      videoPlayerOptions: VideoPlayerOptions(mixWithOthers: false),
    );
    _controller = controller;
    controller.addListener(_onVideoChanged);
    try {
      await controller.initialize();
      await controller.setLooping(true);
      await controller.setVolume(_muted ? 0 : 1);
      if (!mounted || _controller != controller) {
        controller.removeListener(_onVideoChanged);
        await controller.dispose();
        return;
      }
      if (widget.isActive) {
        await controller.play();
      }
      setState(() {
        _loading = false;
      });
    } catch (error) {
      if (mounted && _controller == controller) {
        setState(() {
          _loading = false;
          _loadError = error;
        });
      }
    }
  }

  Future<void> _syncActiveState() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return;
    }
    if (widget.isActive &&
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed) {
      await controller.play();
    } else {
      await controller.pause();
    }
  }

  void _onVideoChanged() {
    final controller = _controller;
    if (!mounted || controller == null) {
      return;
    }
    if (controller.value.hasError && _loadError == null) {
      _loadError = controller.value.errorDescription ?? 'video playback failed';
    }
    setState(() {});
  }

  Future<void> _togglePlayback() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return;
    }
    if (controller.value.isPlaying) {
      await controller.pause();
    } else {
      await controller.play();
    }
  }

  Future<void> _toggleMuted() async {
    final controller = _controller;
    setState(() {
      _muted = !_muted;
    });
    await controller?.setVolume(_muted ? 0 : 1);
  }

  Future<void> _toggleLiked() async {
    final liked = !_liked;
    setState(() {
      _liked = liked;
    });
    try {
      await widget.interactionStore.setLiked(
        widget.content.id,
        widget.content.version,
        liked,
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('点赞状态暂时无法保存')));
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
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('评论已添加，但本地保存失败')));
      }
    }
  }

  Future<T?> _showPanel<T>(WidgetBuilder builder) async {
    final controller = _controller;
    final resumeAfterPanel = controller?.value.isPlaying ?? false;
    if (resumeAfterPanel) {
      await controller?.pause();
    }
    try {
      if (!mounted) {
        return null;
      }
      return await showModalBottomSheet<T>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        backgroundColor: const Color(0xFF161616),
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(8)),
        ),
        builder: builder,
      );
    } finally {
      if (mounted &&
          resumeAfterPanel &&
          widget.isActive &&
          WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed) {
        await controller?.play();
      }
    }
  }

  Future<void> _openComments() async {
    _requestContext(ContextTrigger.comment);
    await _showPanel<void>(
      (context) => CommentsSheet(
        presetComments: _presetComments,
        localComments: _localComments,
        baseCount: widget.content.displayMetrics.commentCount,
        onCommentAdded: _addComment,
      ),
    );
  }

  Future<void> _openShare() async {
    _requestContext(ContextTrigger.share);
    final contact = await _showPanel<SandboxContact>(
      (context) => const ShareSheet(),
    );
    if (mounted && contact != null) {
      setState(() {
        _sessionShareCount += 1;
      });
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('已模拟转发给 ${contact.name}')));
    }
  }

  void _requestContext(ContextTrigger trigger) {
    unawaited(
      _dispatchContext(trigger, _currentViewState(), DateTime.now().toUtc()),
    );
  }

  MediaViewState _currentViewState() {
    final controller = _controller;
    final initialized = controller?.value.isInitialized ?? false;
    final duration = initialized && controller!.value.duration > Duration.zero
        ? controller.value.duration
        : widget.content.duration;
    final durationMs = duration.inMilliseconds.clamp(1, 1 << 31);
    final rawPositionMs = controller?.value.position.inMilliseconds ?? 0;
    return MediaViewState(
      positionMs: rawPositionMs.clamp(0, durationMs),
      durationMs: durationMs,
      isPlaying: controller?.value.isPlaying ?? false,
    );
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

  Future<void> _dispatchContext(
    ContextTrigger trigger,
    MediaViewState viewState,
    DateTime observedAt,
  ) async {
    try {
      await _contextDispatcher.dispatchVideoContext(
        trigger: trigger,
        content: widget.content,
        viewState: viewState,
        observedAt: observedAt,
      );
    } catch (error) {
      debugPrint(
        'CONTEXT_DISPATCH_FAILED trigger=${trigger.wireValue} '
        'error=${error.runtimeType}',
      );
    }
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
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return;
    }
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      _playbackLifecycle.recordInterruption(
        wasPlaying: controller.value.isPlaying,
      );
      unawaited(controller.pause());
    } else if (state == AppLifecycleState.detached) {
      _playbackLifecycle.clear();
      unawaited(controller.pause());
    } else if (state == AppLifecycleState.resumed) {
      if (widget.isActive && _playbackLifecycle.consumeResumeRequest()) {
        unawaited(controller.play());
      }
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    GuardianRequestBridge.deactivate(_guardianRequestHandler);
    if (_ownsContextDispatcher) {
      _contextDispatcher.close();
    }
    final controller = _controller;
    if (controller != null) {
      controller.removeListener(_onVideoChanged);
      unawaited(controller.dispose());
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    final initialized = controller?.value.isInitialized ?? false;
    final playing = controller?.value.isPlaying ?? false;
    final position = controller?.value.position ?? Duration.zero;
    final duration = initialized && controller!.value.duration > Duration.zero
        ? controller.value.duration
        : widget.content.duration;

    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          ColoredBox(
            color: Colors.black,
            child: widget.content.coverUrl != null
                ? Image.network(
                    widget.content.coverUrl.toString(),
                    fit: BoxFit.contain,
                    errorBuilder: (context, error, stackTrace) =>
                        const ColoredBox(
                          color: Color(0xFF111111),
                          child: Center(
                            child: Icon(
                              Icons.image_not_supported_outlined,
                              size: 42,
                            ),
                          ),
                        ),
                  )
                : Image.asset(
              widget.content.coverAssetPath,
              fit: BoxFit.contain,
              errorBuilder: (context, error, stackTrace) => const ColoredBox(
                color: Color(0xFF111111),
                child: Center(
                  child: Icon(Icons.image_not_supported_outlined, size: 42),
                ),
              ),
                  ),
          ),
          if (initialized)
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: _togglePlayback,
              child: FittedBox(
                fit: BoxFit.contain,
                child: SizedBox(
                  width: widget.content.width.toDouble(),
                  height: widget.content.height.toDouble(),
                  child: VideoPlayer(controller!),
                ),
              ),
            ),
          if (_loading)
            const Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CircularProgressIndicator(strokeWidth: 3),
                  SizedBox(height: 14),
                  Text('正在加载视频'),
                ],
              ),
            ),
          if (_loadError != null)
            Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 32),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.cloud_off_outlined, size: 44),
                    const SizedBox(height: 12),
                    const Text(
                      '视频暂时无法播放',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 16),
                    FilledButton.icon(
                      onPressed: _initialize,
                      icon: const Icon(Icons.refresh),
                      label: const Text('重试'),
                    ),
                  ],
                ),
              ),
            ),
          if (initialized && !playing && _loadError == null)
            Center(
              child: IconButton.filledTonal(
                onPressed: _togglePlayback,
                iconSize: 42,
                tooltip: '继续播放',
                icon: const Icon(Icons.play_arrow_rounded),
              ),
            ),
          const _BrandHeader(),
          Positioned(
            right: 8,
            bottom: 152,
            child: _InteractionRail(
              liked: _liked,
              muted: _muted,
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
              onMute: _toggleMuted,
            ),
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: _VideoDetails(
              content: widget.content,
              position: position,
              duration: duration,
              onSeek: initialized ? (value) => controller!.seekTo(value) : null,
            ),
          ),
        ],
      ),
    );
  }
}

class _BrandHeader extends StatelessWidget {
  const _BrandHeader();

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: Align(
        alignment: Alignment.topLeft,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 10, 18, 0),
          child: Row(
            children: [
              const Text(
                'MiMoTrust',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  shadows: [Shadow(color: Colors.black, blurRadius: 8)],
                ),
              ),
              const SizedBox(width: 10),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xCC111111),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: const Color(0x66FFFFFF)),
                ),
                child: const Text(
                  '受控内容',
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _InteractionRail extends StatelessWidget {
  const _InteractionRail({
    required this.liked,
    required this.muted,
    required this.likeCount,
    required this.commentCount,
    required this.shareCount,
    required this.onLike,
    required this.onComment,
    required this.onShare,
    required this.onMute,
  });

  final bool liked;
  final bool muted;
  final int likeCount;
  final int commentCount;
  final int shareCount;
  final VoidCallback onLike;
  final VoidCallback onComment;
  final VoidCallback onShare;
  final VoidCallback onMute;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        _RailAction(
          key: const Key('action-like'),
          tooltip: liked ? '取消点赞' : '点赞',
          label: _compactCount(likeCount),
          icon: liked ? Icons.favorite_rounded : Icons.favorite_border_rounded,
          foregroundColor: liked ? const Color(0xFFFF5A5F) : Colors.white,
          onPressed: onLike,
        ),
        _RailAction(
          key: const Key('action-comment'),
          tooltip: '打开评论',
          label: _compactCount(commentCount),
          icon: Icons.chat_bubble_outline_rounded,
          onPressed: onComment,
        ),
        _RailAction(
          key: const Key('action-share'),
          tooltip: '打开转发',
          label: _compactCount(shareCount),
          icon: Icons.reply_rounded,
          onPressed: onShare,
        ),
        _RailAction(
          key: const Key('action-mute'),
          tooltip: muted ? '打开声音' : '静音',
          label: muted ? '静音' : '声音',
          icon: muted ? Icons.volume_off_rounded : Icons.volume_up_rounded,
          onPressed: onMute,
        ),
      ],
    );
  }

  static String _compactCount(int count) {
    if (count < 10000) {
      return '$count';
    }
    final value = count / 10000;
    return value >= 100 ? '${value.round()}万' : '${value.toStringAsFixed(1)}万';
  }
}

class _RailAction extends StatelessWidget {
  const _RailAction({
    super.key,
    required this.tooltip,
    required this.label,
    required this.icon,
    required this.onPressed,
    this.foregroundColor = Colors.white,
  });

  final String tooltip;
  final String label;
  final IconData icon;
  final VoidCallback onPressed;
  final Color foregroundColor;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 56,
      height: 62,
      child: Column(
        children: [
          SizedBox.square(
            dimension: 44,
            child: IconButton.filledTonal(
              onPressed: onPressed,
              tooltip: tooltip,
              icon: Icon(icon, size: 23),
              style: IconButton.styleFrom(
                fixedSize: const Size.square(44),
                backgroundColor: const Color(0xB3111111),
                foregroundColor: foregroundColor,
              ),
            ),
          ),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 10,
              shadows: [Shadow(color: Colors.black, blurRadius: 4)],
            ),
          ),
        ],
      ),
    );
  }
}

class _VideoDetails extends StatelessWidget {
  const _VideoDetails({
    required this.content,
    required this.position,
    required this.duration,
    required this.onSeek,
  });

  final VideoContent content;
  final Duration position;
  final Duration duration;
  final ValueChanged<Duration>? onSeek;

  @override
  Widget build(BuildContext context) {
    final maximum = duration.inMilliseconds.clamp(1, 1 << 31).toDouble();
    final current = position.inMilliseconds
        .clamp(0, maximum.toInt())
        .toDouble();
    return ColoredBox(
      color: const Color(0xC9000000),
      child: SafeArea(
        top: false,
        minimum: const EdgeInsets.only(bottom: 4),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  Container(
                    width: 34,
                    height: 34,
                    alignment: Alignment.center,
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      color: Color(0xFFFF5A5F),
                    ),
                    child: const Text(
                      'M',
                      style: TextStyle(fontWeight: FontWeight.w800),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      content.author,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ),
                  Text(
                    _publishedDate(content.publishedAt),
                    style: const TextStyle(
                      color: Color(0xFFB8B8B8),
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                content.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                ),
              ),
              Row(
                children: [
                  Text(
                    _duration(position),
                    style: const TextStyle(
                      fontSize: 11,
                      color: Color(0xFFD0D0D0),
                    ),
                  ),
                  Expanded(
                    child: SliderTheme(
                      data: SliderTheme.of(context).copyWith(
                        trackHeight: 2,
                        thumbShape: const RoundSliderThumbShape(
                          enabledThumbRadius: 5,
                        ),
                        overlayShape: const RoundSliderOverlayShape(
                          overlayRadius: 14,
                        ),
                      ),
                      child: Slider(
                        value: current,
                        max: maximum,
                        onChanged: onSeek == null
                            ? null
                            : (value) => onSeek!(
                                Duration(milliseconds: value.round()),
                              ),
                      ),
                    ),
                  ),
                  Text(
                    _duration(duration),
                    style: const TextStyle(
                      fontSize: 11,
                      color: Color(0xFFD0D0D0),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  static String _publishedDate(String value) {
    return value.substring(0, 10).replaceAll('-', '.');
  }

  static String _duration(Duration value) {
    final minutes = value.inMinutes;
    final seconds = value.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }
}

class _ContentStatusView extends StatelessWidget {
  const _ContentStatusView.loading() : onRetry = null;

  const _ContentStatusView.error({required this.onRetry});

  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          const ColoredBox(color: Colors.black),
          const _BrandHeader(),
          Center(
            child: onRetry == null
                ? const CircularProgressIndicator(strokeWidth: 3)
                : Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.inventory_2_outlined, size: 44),
                      const SizedBox(height: 12),
                      const Text(
                        '内容清单暂时不可用',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 16),
                      OutlinedButton.icon(
                        onPressed: onRetry,
                        icon: const Icon(Icons.refresh),
                        label: const Text('重新加载'),
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}
