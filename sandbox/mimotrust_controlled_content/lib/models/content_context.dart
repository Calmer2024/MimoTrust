import 'dart:convert';

enum ContextTrigger {
  comment('comment'),
  share('share');

  const ContextTrigger(this.wireValue);

  final String wireValue;
}

class ContentReference {
  ContentReference({
    required this.contentType,
    required this.contentId,
    required this.contentVersion,
    required this.contentHash,
    required this.canonicalUrl,
  }) {
    if (!const <String>{
      'video',
      'audio',
      'article',
      'rich_article',
      'image_gallery',
    }.contains(contentType)) {
      throw ArgumentError.value(contentType, 'contentType');
    }
    if (!RegExp(r'^[a-z0-9][a-z0-9-]{0,63}$').hasMatch(contentId)) {
      throw ArgumentError.value(contentId, 'contentId');
    }
    if (!RegExp(r'^v[1-9][0-9]*$').hasMatch(contentVersion)) {
      throw ArgumentError.value(contentVersion, 'contentVersion');
    }
    if (!RegExp(r'^[0-9a-f]{64}$').hasMatch(contentHash)) {
      throw ArgumentError.value(contentHash, 'contentHash');
    }
    if (canonicalUrl.scheme != 'https') {
      throw ArgumentError.value(canonicalUrl, 'canonicalUrl');
    }
  }

  final String contentType;
  final String contentId;
  final String contentVersion;
  final String contentHash;
  final Uri canonicalUrl;

  Map<String, Object> toJson() => <String, Object>{
    'content_type': contentType,
    'content_id': contentId,
    'content_version': contentVersion,
    'content_hash': contentHash,
    'canonical_url': canonicalUrl.toString(),
  };
}

class ContentGrant {
  ContentGrant({
    required this.grantCode,
    required this.expiresAt,
    required this.audience,
    required this.scopes,
    required this.exchangeUrl,
    required this.contentReference,
  }) {
    if (grantCode.isEmpty || grantCode.length > 512) {
      throw ArgumentError.value(grantCode.length, 'grantCode.length');
    }
    if (audience != 'mimotrust_guardian_backend') {
      throw ArgumentError.value(audience, 'audience');
    }
    if (scopes.toSet().length != scopes.length ||
        scopes.toSet().difference(const <String>{
          'manifest:read',
          'asset:read',
        }).isNotEmpty ||
        scopes.isEmpty) {
      throw ArgumentError.value(scopes, 'scopes');
    }
    if (!exchangeUrl.hasScheme) {
      throw ArgumentError.value(exchangeUrl, 'exchangeUrl');
    }
  }

  final String grantCode;
  final DateTime expiresAt;
  final String audience;
  final List<String> scopes;
  final Uri exchangeUrl;
  final ContentReference contentReference;

  Map<String, Object> accessJson() => <String, Object>{
    'mode': 'grant_exchange',
    'exchange_url': exchangeUrl.toString(),
    'grant_code': grantCode,
    'audience': audience,
    'expires_at': expiresAt.toUtc().toIso8601String(),
    'scopes': scopes,
  };
}

abstract interface class ContentViewState {
  Map<String, Object> toJson();
}

class MediaViewState implements ContentViewState {
  MediaViewState({
    required this.positionMs,
    required this.durationMs,
    required this.isPlaying,
  }) {
    if (durationMs < 1) {
      throw ArgumentError.value(durationMs, 'durationMs');
    }
    if (positionMs < 0 || positionMs > durationMs) {
      throw ArgumentError.value(positionMs, 'positionMs');
    }
  }

  final int positionMs;
  final int durationMs;
  final bool isPlaying;

  @override
  Map<String, Object> toJson() => <String, Object>{
    'position_ms': positionMs,
    'duration_ms': durationMs,
    'is_playing': isPlaying,
  };
}

class ReadingViewState implements ContentViewState {
  ReadingViewState({required this.scrollRatio, required this.blockIndex}) {
    if (!scrollRatio.isFinite || scrollRatio < 0 || scrollRatio > 1) {
      throw ArgumentError.value(scrollRatio, 'scrollRatio');
    }
    if (blockIndex < 0) {
      throw ArgumentError.value(blockIndex, 'blockIndex');
    }
  }

  final double scrollRatio;
  final int blockIndex;

  @override
  Map<String, Object> toJson() => <String, Object>{
    'scroll_ratio': scrollRatio,
    'block_index': blockIndex,
  };
}

class GalleryViewState implements ContentViewState {
  GalleryViewState({
    required this.activeAssetIndex,
    required this.assetCount,
  }) {
    if (assetCount < 1) {
      throw ArgumentError.value(assetCount, 'assetCount');
    }
    if (activeAssetIndex < 0 || activeAssetIndex >= assetCount) {
      throw ArgumentError.value(activeAssetIndex, 'activeAssetIndex');
    }
  }

  final int activeAssetIndex;
  final int assetCount;

  @override
  Map<String, Object> toJson() => <String, Object>{
    'active_asset_index': activeAssetIndex,
    'asset_count': assetCount,
  };
}

class ContentContext {
  ContentContext({
    required this.eventId,
    required this.trigger,
    required this.grant,
    required this.viewState,
    required this.observedAt,
  }) {
    if (!RegExp(
      r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
      caseSensitive: false,
    ).hasMatch(eventId)) {
      throw ArgumentError.value(eventId, 'eventId');
    }
    if (!grant.expiresAt.isAfter(observedAt)) {
      throw ArgumentError('The grant must expire after observedAt.');
    }
  }

  static const schemaVersion = '2.1';
  static const sourceApp = 'mimotrust_controlled_content';
  static const providerId = 'mimotrust_sandbox';
  static const applicationId = 'com.mimotrust.controlledcontent';
  static const maximumPayloadBytes = 32 * 1024;

  final String eventId;
  final ContextTrigger trigger;
  final ContentGrant grant;
  final ContentViewState viewState;
  final DateTime observedAt;

  Map<String, Object> toJson() => <String, Object>{
    'schema_version': schemaVersion,
    'event_id': eventId,
    'trigger': trigger.wireValue,
    'source_app': sourceApp,
    'provider': const <String, Object>{
      'provider_id': providerId,
      'application_id': applicationId,
    },
    'content_ref': grant.contentReference.toJson(),
    'content_access': grant.accessJson(),
    'view_state': viewState.toJson(),
    'observed_at': observedAt.toUtc().toIso8601String(),
  };

  String toJsonString() {
    final encoded = jsonEncode(toJson());
    if (utf8.encode(encoded).length > maximumPayloadBytes) {
      throw StateError('Content Context exceeds 32 KB.');
    }
    return encoded;
  }
}
