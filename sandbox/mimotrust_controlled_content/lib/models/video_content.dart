import 'dart:convert';

class VideoDisplayMetrics {
  const VideoDisplayMetrics({
    required this.likeCount,
    required this.commentCount,
    required this.shareCount,
  });

  const VideoDisplayMetrics.zero()
    : likeCount = 0,
      commentCount = 0,
      shareCount = 0;

  final int likeCount;
  final int commentCount;
  final int shareCount;

  factory VideoDisplayMetrics.fromRegistry(Object? value) {
    if (value is! Map<String, dynamic>) {
      throw const FormatException('display_metrics must be an object.');
    }
    return VideoDisplayMetrics(
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

class VideoContent {
  const VideoContent({
    required this.id,
    required this.version,
    required this.hash,
    required this.title,
    required this.author,
    required this.publishedAt,
    required this.canonicalUrl,
    required this.videoUrl,
    required this.coverAssetPath,
    required this.duration,
    required this.width,
    required this.height,
    this.displayMetrics = const VideoDisplayMetrics.zero(),
  });

  final String id;
  final String version;
  final String hash;
  final String title;
  final String author;
  final String publishedAt;
  final Uri canonicalUrl;
  final Uri videoUrl;
  final String coverAssetPath;
  final Duration duration;
  final int width;
  final int height;
  final VideoDisplayMetrics displayMetrics;

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
  }) {
    if (manifest['manifest_version'] != '1.0') {
      throw const FormatException('Unsupported Manifest version.');
    }
    final provider = _map(manifest['provider'], 'provider');
    if (provider['provider_id'] != 'mimotrust_sandbox') {
      throw const FormatException('Unexpected content provider.');
    }

    final content = _map(manifest['content'], 'content');
    if (content['content_type'] != 'video') {
      throw const FormatException('Featured content must be a video.');
    }
    final assets = _listOfMaps(manifest['assets'], 'assets');
    final analysis = _singleAsset(assets, 'analysis');
    final cover = _singleAsset(assets, 'cover');
    if (analysis['mime_type'] != 'video/mp4') {
      throw const FormatException('Analysis asset must be video/mp4.');
    }

    final hash = _string(content['content_hash'], 'content.content_hash');
    if (_string(analysis['sha256'], 'analysis.sha256') != hash) {
      throw const FormatException('Content and analysis asset hashes differ.');
    }
    final videoUrl = Uri.tryParse(
      _string(analysis['source_url'], 'analysis.source_url'),
    );
    if (videoUrl == null || videoUrl.scheme != 'https') {
      throw const FormatException('Video URL must use HTTPS.');
    }
    final canonicalUrl = Uri.tryParse(
      _string(content['canonical_url'], 'content.canonical_url'),
    );
    if (canonicalUrl == null || canonicalUrl.scheme != 'https') {
      throw const FormatException('Canonical URL must use HTTPS.');
    }
    final coverStorage = _map(cover['storage'], 'cover.storage');
    if (coverStorage['provider'] != 'local') {
      throw const FormatException('The first-round cover must be local.');
    }

    final durationMs = _positiveInt(
      analysis['duration_ms'],
      'analysis.duration_ms',
    );
    return VideoContent(
      id: _string(content['content_id'], 'content.content_id'),
      version: _string(content['content_version'], 'content.content_version'),
      hash: hash,
      title: _string(content['title'], 'content.title'),
      author: _string(content['author'], 'content.author'),
      publishedAt: _dateTimeString(
        content['published_at'],
        'content.published_at',
      ),
      canonicalUrl: canonicalUrl,
      videoUrl: videoUrl,
      coverAssetPath: _string(
        coverStorage['object_key'],
        'cover.storage.object_key',
      ),
      duration: Duration(milliseconds: durationMs),
      width: _positiveInt(analysis['width'], 'analysis.width'),
      height: _positiveInt(analysis['height'], 'analysis.height'),
      displayMetrics: displayMetrics,
    );
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

  static Map<String, dynamic> _singleAsset(
    List<Map<String, dynamic>> assets,
    String role,
  ) {
    final matching = assets.where((asset) => asset['role'] == role).toList();
    if (matching.length != 1) {
      throw FormatException('Manifest must contain one $role asset.');
    }
    return matching.single;
  }

  static String _string(Object? value, String path) {
    if (value is! String || value.isEmpty) {
      throw FormatException('$path must be a non-empty string.');
    }
    return value;
  }

  static int _positiveInt(Object? value, String path) {
    if (value is! int || value <= 0) {
      throw FormatException('$path must be a positive integer.');
    }
    return value;
  }

  static String _dateTimeString(Object? value, String path) {
    final source = _string(value, path);
    final parsed = DateTime.tryParse(source);
    if (parsed == null) {
      throw FormatException('$path must be an ISO 8601 date-time.');
    }
    return source;
  }
}
