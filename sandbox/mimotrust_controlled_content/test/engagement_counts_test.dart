import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mimotrust_controlled_content/models/content_context.dart';
import 'package:mimotrust_controlled_content/models/sandbox_comment.dart';
import 'package:mimotrust_controlled_content/models/video_content.dart';
import 'package:mimotrust_controlled_content/pages/video_content_page.dart';
import 'package:mimotrust_controlled_content/services/content_grant_client.dart';
import 'package:mimotrust_controlled_content/services/context_dispatcher.dart';
import 'package:mimotrust_controlled_content/services/context_transport.dart';
import 'package:mimotrust_controlled_content/services/local_interaction_store.dart';

void main() {
  testWidgets('counts change locally without adding Context triggers', (
    tester,
  ) async {
    final transport = _RecordingTransport();
    final dispatcher = ContextDispatcher(
      _FakeGrantClient(),
      transport: transport,
    );
    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark(useMaterial3: true),
        home: NetworkVideoPage(
          content: _videoFixture(),
          interactionStore: _MemoryInteractionStore(),
          contextDispatcher: dispatcher,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('100'), findsOneWidget);
    expect(find.text('20'), findsOneWidget);
    expect(find.text('30'), findsOneWidget);

    await tester.tap(find.byKey(const Key('action-like')));
    await tester.pump();
    expect(find.text('101'), findsOneWidget);
    expect(transport.sent, isEmpty);

    await tester.tap(find.byKey(const Key('action-comment')));
    await tester.pumpAndSettle();
    expect(transport.sent.map((item) => item.trigger), <ContextTrigger>[
      ContextTrigger.comment,
    ]);
    await tester.enterText(find.byKey(const Key('comment-input')), '本地新增评论');
    await tester.tap(find.byKey(const Key('comment-submit')));
    await tester.pumpAndSettle();
    expect(find.text('评论 21'), findsOneWidget);
    await tester.tap(find.byType(CloseButton));
    await tester.pumpAndSettle();
    expect(find.text('21'), findsOneWidget);
    expect(transport.sent, hasLength(1));

    await tester.tap(find.byKey(const Key('action-share')));
    await tester.pumpAndSettle();
    expect(transport.sent.map((item) => item.trigger), <ContextTrigger>[
      ContextTrigger.comment,
      ContextTrigger.share,
    ]);
    await tester.tap(find.byKey(const Key('share-contact-0')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('share-submit')));
    await tester.pumpAndSettle();
    expect(find.text('31'), findsOneWidget);
    expect(transport.sent, hasLength(2));

    dispatcher.close();
  });
}

class _RecordingTransport implements ContextTransport {
  final List<ContentContext> sent = <ContentContext>[];

  @override
  Future<void> send(ContentContext context) async {
    sent.add(context);
  }
}

class _FakeGrantClient implements ContentGrantClient {
  @override
  Future<ContentGrant> issueGrant(ContentReference reference) async {
    return ContentGrant(
      grantCode: 'test-grant',
      expiresAt: DateTime.now().toUtc().add(const Duration(minutes: 3)),
      audience: 'mimotrust_guardian_backend',
      scopes: const <String>['manifest:read', 'asset:read'],
      exchangeUrl: Uri.parse('http://127.0.0.1:8787/v1/grants/exchange'),
      contentReference: reference,
    );
  }

  @override
  void close() {}
}

class _MemoryInteractionStore implements InteractionStore {
  bool liked = false;
  final List<SandboxComment> comments = <SandboxComment>[];

  @override
  Future<void> addComment(
    String contentId,
    String contentVersion,
    SandboxComment comment,
  ) async {
    comments.add(comment);
  }

  @override
  Future<List<SandboxComment>> loadComments(
    String contentId,
    String contentVersion,
  ) async => List<SandboxComment>.of(comments);

  @override
  Future<bool> loadLiked(String contentId, String contentVersion) async => liked;

  @override
  Future<void> setLiked(
    String contentId,
    String contentVersion,
    bool value,
  ) async {
    liked = value;
  }
}

VideoContent _videoFixture() {
  return VideoContent(
    id: 'video-001',
    version: 'v1',
    hash: List.filled(64, '0').join(),
    title: '测试视频',
    author: 'MiMoTrust',
    publishedAt: '2026-08-01T00:00:00+08:00',
    canonicalUrl: Uri.parse('https://sandbox.mimotrust.local/video-001'),
    videoUrl: Uri.parse('https://example.test/video.mp4'),
    coverAssetPath: 'assets/images/video-001-cover.png',
    duration: const Duration(seconds: 22),
    width: 720,
    height: 1280,
    displayMetrics: const VideoDisplayMetrics(
      likeCount: 100,
      commentCount: 20,
      shareCount: 30,
    ),
  );
}
