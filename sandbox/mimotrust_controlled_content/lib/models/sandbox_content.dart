import 'dart:convert';

enum SandboxContentType {
  video('video'),
  audio('audio'),
  article('article'),
  richArticle('rich_article'),
  imageGallery('image_gallery');

  const SandboxContentType(this.wireValue);

  final String wireValue;

  static SandboxContentType parse(Object? value) {
    return values.firstWhere(
      (item) => item.wireValue == value,
      orElse: () => throw const FormatException('Unsupported content type.'),
    );
  }
}

class ContentDisplayMetrics {
  const ContentDisplayMetrics({
    required this.likeCount,
    required this.commentCount,
    required this.shareCount,
  });

  const ContentDisplayMetrics.zero()
    : likeCount = 0,
      commentCount = 0,
      shareCount = 0;

  final int likeCount;
  final int commentCount;
  final int shareCount;

  factory ContentDisplayMetrics.fromRegistry(Object? value) {
    if (value is! Map<String, dynamic>) {
      throw const FormatException('display_metrics must be an object.');
    }
    return ContentDisplayMetrics(
      likeCount: _count(value['like_count'], 'display_metrics.like_count'),
      commentCount: _count(
        value['comment_count'],
        'display_metrics.comment_count',
      ),
      shareCount: _count(value['share_count'], 'display_metrics.share_count'),
    );
  }

  static int _count(Object? value, String path) {
    if (value is! int || value < 0) {
      throw FormatException('$path must be a non-negative integer.');
    }
    return value;
  }
}

class VideoDisplayMetrics extends ContentDisplayMetrics {
  const VideoDisplayMetrics({
    required super.likeCount,
    required super.commentCount,
    required super.shareCount,
  });

  const VideoDisplayMetrics.zero()
    : super(likeCount: 0, commentCount: 0, shareCount: 0);

  factory VideoDisplayMetrics.fromRegistry(Object? value) {
    final metrics = ContentDisplayMetrics.fromRegistry(value);
    return VideoDisplayMetrics(
      likeCount: metrics.likeCount,
      commentCount: metrics.commentCount,
      shareCount: metrics.shareCount,
    );
  }
}

class ContentAsset {
  const ContentAsset({
    required this.id,
    required this.role,
    required this.mimeType,
    required this.sourceUrl,
    required this.sha256,
    required this.sizeBytes,
    required this.order,
    this.duration,
    this.width,
    this.height,
    this.localAssetPath,
  });

  final String id;
  final String role;
  final String mimeType;
  final Uri sourceUrl;
  final String sha256;
  final int sizeBytes;
  final int order;
  final Duration? duration;
  final int? width;
  final int? height;
  final String? localAssetPath;
}

sealed class SandboxContent {
  const SandboxContent({
    required this.type,
    required this.id,
    required this.version,
    required this.hash,
    required this.title,
    required this.author,
    required this.publishedAt,
    required this.canonicalUrl,
    required this.assets,
    required this.displayMetrics,
  });

  final SandboxContentType type;
  final String id;
  final String version;
  final String hash;
  final String title;
  final String author;
  final String publishedAt;
  final Uri canonicalUrl;
  final List<ContentAsset> assets;
  final ContentDisplayMetrics displayMetrics;

  String get contentType => type.wireValue;

  factory SandboxContent.fromManifest(
    Map<String, dynamic> manifest, {
    ContentDisplayMetrics displayMetrics = const ContentDisplayMetrics.zero(),
    bool useNetworkAssets = false,
  }) {
    return _ManifestParser(
      manifest,
      displayMetrics: displayMetrics,
      useNetworkAssets: useNetworkAssets,
    ).parse();
  }
}

class VideoContent extends SandboxContent {
  VideoContent({
    required super.id,
    required super.version,
    required super.hash,
    required super.title,
    required super.author,
    required super.publishedAt,
    required super.canonicalUrl,
    required this.videoUrl,
    required this.coverAssetPath,
    required this.duration,
    required this.width,
    required this.height,
    this.coverUrl,
    VideoDisplayMetrics displayMetrics = const VideoDisplayMetrics.zero(),
    super.assets = const <ContentAsset>[],
  }) : super(
         type: SandboxContentType.video,
         displayMetrics: displayMetrics,
       );

  final Uri videoUrl;
  final String coverAssetPath;
  final Uri? coverUrl;
  final Duration duration;
  final int width;
  final int height;

  factory VideoContent.fromManifestString(
    String source, {
    VideoDisplayMetrics displayMetrics = const VideoDisplayMetrics.zero(),
  }) {
    final Object? decoded = jsonDecode(source);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Manifest root must be an object.');
    }
    return VideoContent.fromManifest(decoded, displayMetrics: displayMetrics);
  }

  factory VideoContent.fromManifest(
    Map<String, dynamic> manifest, {
    VideoDisplayMetrics displayMetrics = const VideoDisplayMetrics.zero(),
    bool useNetworkAssets = false,
  }) {
    final parsed = SandboxContent.fromManifest(
      manifest,
      displayMetrics: displayMetrics,
      useNetworkAssets: useNetworkAssets,
    );
    if (parsed is! VideoContent) {
      throw const FormatException('Featured content must be a video.');
    }
    return parsed;
  }
}

class AudioContent extends SandboxContent {
  const AudioContent({
    required super.id,
    required super.version,
    required super.hash,
    required super.title,
    required super.author,
    required super.publishedAt,
    required super.canonicalUrl,
    required super.assets,
    required super.displayMetrics,
    required this.audioUrl,
    required this.duration,
    this.coverUrl,
  }) : super(type: SandboxContentType.audio);

  final Uri audioUrl;
  final Duration duration;
  final Uri? coverUrl;
}

class ArticleContent extends SandboxContent {
  const ArticleContent({
    required super.id,
    required super.version,
    required super.hash,
    required super.title,
    required super.author,
    required super.publishedAt,
    required super.canonicalUrl,
    required super.assets,
    required super.displayMetrics,
    required this.bodyUrl,
    required this.bodyMimeType,
  }) : super(type: SandboxContentType.article);

  final Uri bodyUrl;
  final String bodyMimeType;
}

class RichArticleBlock {
  const RichArticleBlock({
    required this.index,
    required this.type,
    this.text,
    this.asset,
  });

  final int index;
  final String type;
  final String? text;
  final ContentAsset? asset;
}

class RichArticleContent extends SandboxContent {
  const RichArticleContent({
    required super.id,
    required super.version,
    required super.hash,
    required super.title,
    required super.author,
    required super.publishedAt,
    required super.canonicalUrl,
    required super.assets,
    required super.displayMetrics,
    required this.blocks,
  }) : super(type: SandboxContentType.richArticle);

  final List<RichArticleBlock> blocks;
}

class ImageGalleryContent extends SandboxContent {
  const ImageGalleryContent({
    required super.id,
    required super.version,
    required super.hash,
    required super.title,
    required super.author,
    required super.publishedAt,
    required super.canonicalUrl,
    required super.assets,
    required super.displayMetrics,
    required this.images,
  }) : super(type: SandboxContentType.imageGallery);

  final List<ContentAsset> images;
}

class _ManifestParser {
  _ManifestParser(
    this.manifest, {
    required this.displayMetrics,
    required this.useNetworkAssets,
  });

  final Map<String, dynamic> manifest;
  final ContentDisplayMetrics displayMetrics;
  final bool useNetworkAssets;

  SandboxContent parse() {
    if (manifest['manifest_version'] != '1.0') {
      throw const FormatException('Unsupported Manifest version.');
    }
    final provider = _map(manifest['provider'], 'provider');
    if (provider['provider_id'] != 'mimotrust_sandbox') {
      throw const FormatException('Unexpected content provider.');
    }
    final content = _map(manifest['content'], 'content');
    final type = SandboxContentType.parse(content['content_type']);
    final common = _common(content);
    final assets = _assets(manifest['assets']);

    return switch (type) {
      SandboxContentType.video => _video(common, assets),
      SandboxContentType.audio => _audio(common, assets),
      SandboxContentType.article => _article(common, assets, content),
      SandboxContentType.richArticle => _richArticle(common, assets, content),
      SandboxContentType.imageGallery => _gallery(common, assets, content),
    };
  }

  Map<String, Object> _common(Map<String, dynamic> content) {
    final hash = _string(content['content_hash'], 'content.content_hash');
    if (!RegExp(r'^[0-9a-f]{64}$').hasMatch(hash)) {
      throw const FormatException('content.content_hash must be SHA-256.');
    }
    final canonicalUrl = _uri(
      content['canonical_url'],
      'content.canonical_url',
      httpsOnly: true,
    );
    final publishedAt = _string(content['published_at'], 'content.published_at');
    if (DateTime.tryParse(publishedAt) == null) {
      throw const FormatException('content.published_at must be ISO 8601.');
    }
    return <String, Object>{
      'id': _string(content['content_id'], 'content.content_id'),
      'version': _string(content['content_version'], 'content.content_version'),
      'hash': hash,
      'title': _string(content['title'], 'content.title'),
      'author': _string(content['author'], 'content.author'),
      'publishedAt': publishedAt,
      'canonicalUrl': canonicalUrl,
    };
  }

  List<ContentAsset> _assets(Object? value) {
    final rawAssets = _listOfMaps(value, 'assets');
    final assets = <ContentAsset>[];
    for (var index = 0; index < rawAssets.length; index += 1) {
      final raw = rawAssets[index];
      final storage = raw['storage'] is Map<String, dynamic>
          ? raw['storage'] as Map<String, dynamic>
          : const <String, dynamic>{};
      assets.add(
        ContentAsset(
          id: _string(raw['asset_id'], 'assets[$index].asset_id'),
          role: _string(raw['role'], 'assets[$index].role'),
          mimeType: _string(raw['mime_type'], 'assets[$index].mime_type'),
          sourceUrl: _uri(raw['source_url'], 'assets[$index].source_url'),
          sha256: _sha256(raw['sha256'], 'assets[$index].sha256'),
          sizeBytes: _positiveInt(
            raw['size_bytes'],
            'assets[$index].size_bytes',
          ),
          order: raw['order'] is int ? raw['order'] as int : index,
          duration: raw['duration_ms'] is int
              ? Duration(milliseconds: raw['duration_ms'] as int)
              : null,
          width: raw['width'] is int ? raw['width'] as int : null,
          height: raw['height'] is int ? raw['height'] as int : null,
          localAssetPath: storage['provider'] == 'local'
              ? storage['object_key'] as String?
              : null,
        ),
      );
    }
    assets.sort((left, right) => left.order.compareTo(right.order));
    return List<ContentAsset>.unmodifiable(assets);
  }

  VideoContent _video(Map<String, Object> common, List<ContentAsset> assets) {
    final analysis = _singleAsset(assets, 'analysis');
    if (analysis.mimeType != 'video/mp4' || analysis.sha256 != common['hash']) {
      throw const FormatException('Invalid video analysis asset.');
    }
    final duration = analysis.duration;
    final width = analysis.width;
    final height = analysis.height;
    if (duration == null || width == null || height == null) {
      throw const FormatException('Video dimensions and duration are required.');
    }
    final cover = _optionalSingleAsset(assets, 'cover');
    return VideoContent(
      id: common['id']! as String,
      version: common['version']! as String,
      hash: common['hash']! as String,
      title: common['title']! as String,
      author: common['author']! as String,
      publishedAt: common['publishedAt']! as String,
      canonicalUrl: common['canonicalUrl']! as Uri,
      videoUrl: analysis.sourceUrl,
      coverAssetPath: cover?.localAssetPath ?? '',
      coverUrl: useNetworkAssets ? cover?.sourceUrl : null,
      duration: duration,
      width: width,
      height: height,
      displayMetrics: VideoDisplayMetrics(
        likeCount: displayMetrics.likeCount,
        commentCount: displayMetrics.commentCount,
        shareCount: displayMetrics.shareCount,
      ),
      assets: assets,
    );
  }

  AudioContent _audio(Map<String, Object> common, List<ContentAsset> assets) {
    final analysis = _singleAsset(assets, 'analysis');
    if (!analysis.mimeType.startsWith('audio/') || analysis.sha256 != common['hash']) {
      throw const FormatException('Invalid audio analysis asset.');
    }
    if (analysis.duration == null) {
      throw const FormatException('Audio duration is required.');
    }
    return AudioContent(
      id: common['id']! as String,
      version: common['version']! as String,
      hash: common['hash']! as String,
      title: common['title']! as String,
      author: common['author']! as String,
      publishedAt: common['publishedAt']! as String,
      canonicalUrl: common['canonicalUrl']! as Uri,
      assets: assets,
      displayMetrics: displayMetrics,
      audioUrl: analysis.sourceUrl,
      duration: analysis.duration!,
      coverUrl: _optionalSingleAsset(assets, 'cover')?.sourceUrl,
    );
  }

  ArticleContent _article(
    Map<String, Object> common,
    List<ContentAsset> assets,
    Map<String, dynamic> content,
  ) {
    final bodyId = _string(content['body_asset_id'], 'content.body_asset_id');
    final body = assets.where((asset) => asset.id == bodyId).toList();
    if (body.length != 1 ||
        !const <String>{'text/plain', 'text/markdown'}.contains(body.single.mimeType) ||
        body.single.sha256 != common['hash']) {
      throw const FormatException('Invalid article body asset.');
    }
    return ArticleContent(
      id: common['id']! as String,
      version: common['version']! as String,
      hash: common['hash']! as String,
      title: common['title']! as String,
      author: common['author']! as String,
      publishedAt: common['publishedAt']! as String,
      canonicalUrl: common['canonicalUrl']! as Uri,
      assets: assets,
      displayMetrics: displayMetrics,
      bodyUrl: body.single.sourceUrl,
      bodyMimeType: body.single.mimeType,
    );
  }

  RichArticleContent _richArticle(
    Map<String, Object> common,
    List<ContentAsset> assets,
    Map<String, dynamic> content,
  ) {
    final rawBlocks = _listOfMaps(content['blocks'], 'content.blocks');
    final blocks = <RichArticleBlock>[];
    for (var index = 0; index < rawBlocks.length; index += 1) {
      final raw = rawBlocks[index];
      if (raw['block_index'] != index) {
        throw const FormatException('Rich article block indexes must be ordered.');
      }
      if (raw['block_type'] == 'text') {
        blocks.add(
          RichArticleBlock(
            index: index,
            type: 'text',
            text: _string(raw['text'], 'content.blocks[$index].text'),
          ),
        );
      } else if (raw['block_type'] == 'image') {
        final assetId = _string(
          raw['asset_id'],
          'content.blocks[$index].asset_id',
        );
        final matching = assets.where((asset) => asset.id == assetId).toList();
        if (matching.length != 1 || !matching.single.mimeType.startsWith('image/')) {
          throw const FormatException('Rich article block references an invalid image.');
        }
        blocks.add(
          RichArticleBlock(index: index, type: 'image', asset: matching.single),
        );
      } else {
        throw const FormatException('Unsupported rich article block type.');
      }
    }
    return RichArticleContent(
      id: common['id']! as String,
      version: common['version']! as String,
      hash: common['hash']! as String,
      title: common['title']! as String,
      author: common['author']! as String,
      publishedAt: common['publishedAt']! as String,
      canonicalUrl: common['canonicalUrl']! as Uri,
      assets: assets,
      displayMetrics: displayMetrics,
      blocks: List<RichArticleBlock>.unmodifiable(blocks),
    );
  }

  ImageGalleryContent _gallery(
    Map<String, Object> common,
    List<ContentAsset> assets,
    Map<String, dynamic> content,
  ) {
    final analysis = assets
        .where(
          (asset) => asset.role == 'analysis' && asset.mimeType.startsWith('image/'),
        )
        .toList();
    if (analysis.isEmpty) {
      throw const FormatException('Image gallery requires images.');
    }
    final rawOrder = content['asset_order'];
    if (rawOrder is List) {
      final positions = <String, int>{};
      for (var index = 0; index < rawOrder.length; index += 1) {
        if (rawOrder[index] is String) positions[rawOrder[index] as String] = index;
      }
      analysis.sort(
        (left, right) => (positions[left.id] ?? 1 << 30).compareTo(
          positions[right.id] ?? 1 << 30,
        ),
      );
    }
    return ImageGalleryContent(
      id: common['id']! as String,
      version: common['version']! as String,
      hash: common['hash']! as String,
      title: common['title']! as String,
      author: common['author']! as String,
      publishedAt: common['publishedAt']! as String,
      canonicalUrl: common['canonicalUrl']! as Uri,
      assets: assets,
      displayMetrics: displayMetrics,
      images: List<ContentAsset>.unmodifiable(analysis),
    );
  }

  static ContentAsset _singleAsset(List<ContentAsset> assets, String role) {
    final matching = assets.where((asset) => asset.role == role).toList();
    if (matching.length != 1) {
      throw FormatException('Manifest must contain one $role asset.');
    }
    return matching.single;
  }

  static ContentAsset? _optionalSingleAsset(
    List<ContentAsset> assets,
    String role,
  ) {
    final matching = assets.where((asset) => asset.role == role).toList();
    if (matching.length > 1) {
      throw FormatException('Manifest may contain at most one $role asset.');
    }
    return matching.firstOrNull;
  }

  static Map<String, dynamic> _map(Object? value, String path) {
    if (value is! Map<String, dynamic>) {
      throw FormatException('$path must be an object.');
    }
    return value;
  }

  static List<Map<String, dynamic>> _listOfMaps(Object? value, String path) {
    if (value is! List || value.isEmpty) {
      throw FormatException('$path must be a non-empty array.');
    }
    return value.map((item) => _map(item, '$path item')).toList();
  }

  static String _string(Object? value, String path) {
    if (value is! String || value.isEmpty) {
      throw FormatException('$path must be a non-empty string.');
    }
    return value;
  }

  static String _sha256(Object? value, String path) {
    final result = _string(value, path);
    if (!RegExp(r'^[0-9a-f]{64}$').hasMatch(result)) {
      throw FormatException('$path must be SHA-256.');
    }
    return result;
  }

  static int _positiveInt(Object? value, String path) {
    if (value is! int || value <= 0) {
      throw FormatException('$path must be a positive integer.');
    }
    return value;
  }

  static Uri _uri(Object? value, String path, {bool httpsOnly = false}) {
    final uri = Uri.tryParse(_string(value, path));
    if (uri == null || !uri.hasAuthority || (httpsOnly ? uri.scheme != 'https' : !{'http', 'https'}.contains(uri.scheme))) {
      throw FormatException('$path must be a valid ${httpsOnly ? 'HTTPS ' : ''}URL.');
    }
    return uri;
  }
}
