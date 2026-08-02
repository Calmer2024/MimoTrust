import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mimotrust_controlled_content/models/sandbox_content.dart';
import 'package:mimotrust_controlled_content/pages/content_preview_page.dart';
import 'package:mimotrust_controlled_content/pages/non_video_content_page.dart';

void main() {
  testWidgets('article Feed item is a non-scrolling preview', (tester) async {
    var opened = false;
    await tester.pumpWidget(
      MaterialApp(
        home: ContentPreviewPage(
          content: _articleFixture(),
          onOpen: () => opened = true,
        ),
      ),
    );

    expect(find.byKey(const Key('article-scroll')), findsNothing);
    expect(find.text('测试文章'), findsOneWidget);
    await tester.tap(find.byKey(const Key('open-content-article-001')));
    expect(opened, isTrue);
  });

  testWidgets('article detail reports reading offset and has bottom actions', (
    tester,
  ) async {
    var lastOffset = 0.0;
    final body = List<String>.generate(
      80,
      (index) => '第 $index 段。这是一段用于验证独立阅读页滚动行为的正文内容。',
    ).join('\n\n');
    await tester.pumpWidget(
      MaterialApp(
        home: NonVideoContentPage(
          content: _articleFixture(),
          isActive: true,
          isDetail: true,
          initialReadingOffset: 240,
          httpClient: MockClient(
            (request) async => http.Response.bytes(
              utf8.encode(body),
              200,
              headers: const <String, String>{
                'content-type': 'text/plain; charset=utf-8',
              },
            ),
          ),
          onReadingOffsetChanged: (offset) => lastOffset = offset,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('reading-progress')), findsOneWidget);
    expect(find.byKey(const Key('action-comment')), findsOneWidget);
    final scrollable = tester.state<ScrollableState>(
      find.descendant(
        of: find.byKey(const Key('article-scroll')),
        matching: find.byType(Scrollable),
      ),
    );
    expect(scrollable.position.maxScrollExtent, greaterThan(0));
    expect(scrollable.position.pixels, closeTo(240, 0.1));
    await tester.dragFrom(const Offset(200, 300), const Offset(0, -500));
    await tester.pumpAndSettle();
    expect(lastOffset, greaterThan(0));
  });

  testWidgets('gallery detail preserves the active image index', (tester) async {
    var activeIndex = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: NonVideoContentPage(
          content: _galleryFixture(),
          isActive: true,
          isDetail: true,
          onGalleryIndexChanged: (index) => activeIndex = index,
        ),
      ),
    );
    await tester.pump();

    expect(find.text('1 / 2  ·  测试作者'), findsOneWidget);
    await tester.drag(
      find.byKey(const Key('gallery-pages')),
      const Offset(-500, 0),
    );
    await tester.pumpAndSettle();
    expect(activeIndex, 1);
    expect(find.text('2 / 2  ·  测试作者'), findsOneWidget);
  });
}

ArticleContent _articleFixture() {
  const metrics = ContentDisplayMetrics.zero();
  return ArticleContent(
    id: 'article-001',
    version: 'v1',
    hash: List<String>.filled(64, 'a').join(),
    title: '测试文章',
    author: '测试作者',
    publishedAt: '2026-08-02T00:00:00+08:00',
    canonicalUrl: Uri.parse(
      'https://sandbox.mimotrust.local/content/article-001',
    ),
    assets: const <ContentAsset>[],
    displayMetrics: metrics,
    bodyUrl: Uri.parse('https://example.test/article.txt'),
    bodyMimeType: 'text/plain',
  );
}

ImageGalleryContent _galleryFixture() {
  ContentAsset image(String id) => ContentAsset(
    id: id,
    role: 'analysis',
    mimeType: 'image/png',
    sourceUrl: Uri.parse('https://example.test/$id.png'),
    sha256: List<String>.filled(64, 'b').join(),
    sizeBytes: 128,
    order: id == 'image-001' ? 0 : 1,
  );
  final images = <ContentAsset>[image('image-001'), image('image-002')];
  return ImageGalleryContent(
    id: 'gallery-001',
    version: 'v1',
    hash: List<String>.filled(64, 'c').join(),
    title: '测试图集',
    author: '测试作者',
    publishedAt: '2026-08-02T00:00:00+08:00',
    canonicalUrl: Uri.parse(
      'https://sandbox.mimotrust.local/content/gallery-001',
    ),
    assets: images,
    displayMetrics: const ContentDisplayMetrics.zero(),
    images: images,
  );
}
