import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mimotrust_controlled_content/models/video_content.dart';
import 'package:mimotrust_controlled_content/services/content_repository.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('bundled video-001 Manifest parses with the fixed identity', () async {
    final source = await rootBundle.loadString(
      'assets/data/manifests/video-001.v1.json',
    );
    final content = VideoContent.fromManifestString(source);

    expect(content.id, 'video-001');
    expect(content.version, 'v1');
    expect(content.duration, const Duration(milliseconds: 22467));
    expect(content.width, 720);
    expect(content.height, 1280);
    expect(
      content.canonicalUrl,
      Uri.parse('https://sandbox.mimotrust.local/content/video-001'),
    );
    expect(
      content.hash,
      '0f6c57d2f3f2772a3abfde87b52123c45228a420e40cada19035dd26afa2f734',
    );
    expect(content.coverAssetPath, 'assets/images/video-001-cover.png');
  });

  test('Manifest rejects a content and asset hash mismatch', () async {
    final source = await rootBundle.loadString(
      'assets/data/manifests/video-001.v1.json',
    );
    final manifest = jsonDecode(source) as Map<String, dynamic>;
    final assets = manifest['assets'] as List<dynamic>;
    final analysis = assets.first as Map<String, dynamic>;
    analysis['sha256'] = List.filled(64, 'a').join();

    expect(
      () => VideoContent.fromManifest(manifest),
      throwsA(isA<FormatException>()),
    );
  });

  test('bundled registry loads three ordered videos and display metrics', () async {
    final contents = await ContentRepository().loadVideoFeed();

    expect(
      contents.map((content) => content.id),
      <String>['video-001', 'video-002', 'video-003'],
    );
    expect(contents[0].displayMetrics.likeCount, 1284);
    expect(contents[1].duration, const Duration(milliseconds: 19301));
    expect(contents[1].hash, startsWith('6c49aeeffcfebf35'));
    expect(contents[2].duration, const Duration(milliseconds: 28320));
    expect(contents[2].height, 1066);
    expect(contents[2].displayMetrics.commentCount, 173);
  });
}
