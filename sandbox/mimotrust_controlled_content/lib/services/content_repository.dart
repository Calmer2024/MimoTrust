import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

import '../models/sandbox_content.dart';

class ContentRepository {
  ContentRepository({
    AssetBundle? bundle,
    http.Client? httpClient,
    Uri? gatewayBaseUrl,
    this.timeout = const Duration(seconds: 3),
  }) : _bundle = bundle ?? rootBundle,
       _httpClient = httpClient ?? http.Client(),
       gatewayBaseUrl =
           gatewayBaseUrl ??
           Uri.parse(
             const String.fromEnvironment(
               'MIMOTRUST_GATEWAY_URL',
               defaultValue: 'http://127.0.0.1:8787',
             ),
           );

  final AssetBundle _bundle;
  final http.Client _httpClient;
  final Uri gatewayBaseUrl;
  final Duration timeout;

  Future<List<SandboxContent>> loadContentFeed() async {
    try {
      return await loadRemoteFeed();
    } catch (error) {
      debugPrint('REMOTE_FEED_UNAVAILABLE error=${error.runtimeType}');
      return loadBundledFeed();
    }
  }

  Future<List<SandboxContent>> loadRemoteFeed() async {
    late final http.Response response;
    try {
      response = await _httpClient
          .get(gatewayBaseUrl.resolve('/v1/feed'))
          .timeout(timeout);
    } on TimeoutException {
      throw const ContentFeedException('FEED_TIMEOUT');
    } on http.ClientException {
      throw const ContentFeedException('FEED_UNAVAILABLE');
    }
    if (response.statusCode != 200) {
      throw ContentFeedException('FEED_HTTP_${response.statusCode}');
    }

    final Object? decoded;
    try {
      decoded = jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw const ContentFeedException('INVALID_FEED_JSON');
    }
    if (decoded is! Map<String, dynamic> ||
        decoded['registry_version'] != '1.0' ||
        decoded['provider_id'] != 'mimotrust_sandbox' ||
        decoded['contents'] is! List) {
      throw const ContentFeedException('UNSUPPORTED_FEED');
    }

    final parsed = <({int order, SandboxContent content})>[];
    for (final raw in decoded['contents'] as List<dynamic>) {
      try {
        if (raw is! Map<String, dynamic>) {
          throw const FormatException('Feed item must be an object.');
        }
        final manifest = raw['manifest'];
        if (manifest is! Map<String, dynamic>) {
          throw const FormatException('Feed item Manifest is missing.');
        }
        final content = SandboxContent.fromManifest(
          manifest,
          displayMetrics: ContentDisplayMetrics.fromRegistry(
            raw['display_metrics'],
          ),
          useNetworkAssets: true,
        );
        if (content.id != raw['content_id'] ||
            content.version != raw['content_version'] ||
            content.contentType != raw['content_type']) {
          throw const FormatException('Feed and Manifest identities differ.');
        }
        parsed.add((
          order: raw['display_order'] is int
              ? raw['display_order'] as int
              : 1 << 30,
          content: content,
        ));
      } catch (error) {
        debugPrint('REMOTE_FEED_ITEM_SKIPPED error=${error.runtimeType}');
      }
    }
    parsed.sort((left, right) => left.order.compareTo(right.order));
    if (parsed.isEmpty) {
      throw const ContentFeedException('NO_VALID_REMOTE_CONTENT');
    }
    return List<SandboxContent>.unmodifiable(
      parsed.map((item) => item.content),
    );
  }

  Future<List<SandboxContent>> loadBundledFeed() async {
    return List<SandboxContent>.unmodifiable(await loadVideoFeed());
  }

  Future<List<VideoContent>> loadVideoFeed() async {
    final registrySource = await _bundle.loadString(
      'assets/data/registry.json',
    );
    final Object? decoded = jsonDecode(registrySource);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Registry root must be an object.');
    }
    if (decoded['registry_version'] != '1.0' ||
        decoded['provider_id'] != 'mimotrust_sandbox') {
      throw const FormatException('Unsupported content registry.');
    }
    final entries = decoded['contents'];
    if (entries is! List) {
      throw const FormatException('Registry contents must be an array.');
    }
    final videos =
        entries
            .whereType<Map<String, dynamic>>()
            .where(
              (entry) =>
                  entry['status'] == 'active' &&
                  entry['content_type'] == 'video',
            )
            .toList()
          ..sort((a, b) => _displayOrder(a).compareTo(_displayOrder(b)));
    if (videos.isEmpty) {
      throw const FormatException('No active video is registered.');
    }
    final contents = <VideoContent>[];
    for (final selected in videos) {
      final manifestPath = selected['manifest_path'];
      if (manifestPath is! String || manifestPath.isEmpty) {
        throw const FormatException('Registry manifest path is missing.');
      }
      final manifestSource = await _bundle.loadString(
        'assets/data/$manifestPath',
      );
      final content = VideoContent.fromManifestString(
        manifestSource,
        displayMetrics: VideoDisplayMetrics.fromRegistry(
          selected['display_metrics'],
        ),
      );
      if (content.id != selected['content_id'] ||
          content.version != selected['content_version']) {
        throw const FormatException(
          'Registry and Manifest identities differ.',
        );
      }
      contents.add(content);
    }
    return List<VideoContent>.unmodifiable(contents);
  }

  Future<VideoContent> loadFeaturedVideo() async {
    return (await loadVideoFeed()).first;
  }

  void close() => _httpClient.close();

  static int _displayOrder(Map<String, dynamic> entry) {
    final value = entry['display_order'];
    return value is int ? value : 1 << 30;
  }
}

class ContentFeedException implements Exception {
  const ContentFeedException(this.code);

  final String code;

  @override
  String toString() => 'ContentFeedException($code)';
}
