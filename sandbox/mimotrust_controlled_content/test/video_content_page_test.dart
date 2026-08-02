import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mimotrust_controlled_content/main.dart';
import 'package:mimotrust_controlled_content/models/video_content.dart';

void main() {
  testWidgets('App resolves video-001 through the bundled registry', (
    tester,
  ) async {
    await tester.pumpWidget(
      MiMoTrustApp(
        videoBuilder: (content) =>
            Material(child: Text('${content.id}:${content.title}')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('video-001:SkyNomad 澎程事故传言'), findsOneWidget);
  });

  testWidgets('Content load failure can be retried without restarting', (
    tester,
  ) async {
    var attempts = 0;
    Future<VideoContent> load() async {
      attempts += 1;
      if (attempts == 1) {
        throw const FormatException('fixture failure');
      }
      return _videoFixture();
    }

    await tester.pumpWidget(
      MiMoTrustApp(
        loadFeaturedVideo: load,
        videoBuilder: (content) => Material(child: Text(content.id)),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('内容清单暂时不可用'), findsOneWidget);

    await tester.tap(find.text('重新加载'));
    await tester.pumpAndSettle();
    expect(find.text('video-001'), findsOneWidget);
    expect(attempts, 2);
  });

  testWidgets('vertical feed moves through all three bundled videos', (
    tester,
  ) async {
    await tester.pumpWidget(
      MiMoTrustApp(
        loadVideoFeed: () async => <VideoContent>[
          _videoFixture(id: 'video-001', title: '视频一'),
          _videoFixture(id: 'video-002', title: '视频二'),
          _videoFixture(id: 'video-003', title: '视频三'),
        ],
        videoBuilder: (content) => Material(
          child: Center(child: Text('${content.id}:${content.title}')),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('video-001:').hitTestable(), findsOneWidget);
    await tester.drag(find.byKey(const Key('video-feed')), const Offset(0, -500));
    await tester.pumpAndSettle();
    expect(find.textContaining('video-002:').hitTestable(), findsOneWidget);
    await tester.drag(find.byKey(const Key('video-feed')), const Offset(0, -500));
    await tester.pumpAndSettle();
    expect(find.textContaining('video-003:').hitTestable(), findsOneWidget);
  });
}

VideoContent _videoFixture({String id = 'video-001', String title = '测试视频'}) {
  return VideoContent(
    id: id,
    version: 'v1',
    hash: List.filled(64, '0').join(),
    title: title,
    author: 'MiMoTrust',
    publishedAt: '2026-08-01T00:00:00+08:00',
    canonicalUrl: Uri.parse(
      'https://sandbox.mimotrust.local/content/$id',
    ),
    videoUrl: Uri.parse('https://example.test/video.mp4'),
    coverAssetPath: 'assets/images/video-001-cover.png',
    duration: const Duration(seconds: 22),
    width: 720,
    height: 1280,
  );
}
