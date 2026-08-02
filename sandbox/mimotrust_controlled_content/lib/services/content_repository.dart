import 'dart:convert';

import 'package:flutter/services.dart';

import '../models/video_content.dart';

class ContentRepository {
  ContentRepository({AssetBundle? bundle}) : _bundle = bundle ?? rootBundle;

  final AssetBundle _bundle;

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

  static int _displayOrder(Map<String, dynamic> entry) {
    final value = entry['display_order'];
    return value is int ? value : 1 << 30;
  }
}
