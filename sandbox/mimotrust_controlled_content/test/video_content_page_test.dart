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

  testWidgets('refresh keeps the current Feed page', (tester) async {
    var attempts = 0;
    await tester.pumpWidget(
      MiMoTrustApp(
        loadVideoFeed: () async {
          attempts += 1;
          return <VideoContent>[
            _videoFixture(id: 'video-001', title: '视频一'),
            _videoFixture(id: 'video-002', title: '视频二'),
            _videoFixture(id: 'video-003', title: '视频三'),
          ];
        },
        videoBuilder: (content) => Material(
          child: Center(child: Text('${content.id}:${content.title}')),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.drag(find.byKey(const Key('video-feed')), const Offset(0, -500));
    await tester.pumpAndSettle();
    expect(find.textContaining('video-002:').hitTestable(), findsOneWidget);

    await tester.tap(find.byKey(const Key('refresh-feed')));
    await tester.pumpAndSettle();

    expect(attempts, 2);
    expect(find.textContaining('video-002:').hitTestable(), findsOneWidget);
  });

  testWidgets('rich article preview opens a separate reader and returns', (
    tester,
  ) async {
    final article = _richArticleFixture();
    await tester.pumpWidget(
      MiMoTrustApp(loadContentFeed: () async => <SandboxContent>[article]),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('rich-article-scroll')), findsNothing);
    expect(find.byKey(const Key('open-content-rich-001')), findsOneWidget);

    await tester.tap(find.byKey(const Key('open-content-rich-001')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rich-article-scroll')), findsOneWidget);
    expect(find.byKey(const Key('content-detail-back')), findsOneWidget);

    await tester.tap(find.byKey(const Key('content-detail-back')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('open-content-rich-001')), findsOneWidget);
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

RichArticleContent _richArticleFixture() {
  return RichArticleContent(
    id: 'rich-001',
    version: 'v1',
    hash: List<String>.filled(64, 'a').join(),
    title: '测试图文',
    author: '测试作者',
    publishedAt: '2026-08-02T00:00:00+08:00',
    canonicalUrl: Uri.parse(
      'https://sandbox.mimotrust.local/content/rich-001',
    ),
    assets: const <ContentAsset>[],
    displayMetrics: const ContentDisplayMetrics.zero(),
    blocks: const <RichArticleBlock>[
      RichArticleBlock(index: 0, type: 'text', text: '第一段图文正文'),
      RichArticleBlock(index: 1, type: 'text', text: '第二段图文正文'),
    ],
  );
}
