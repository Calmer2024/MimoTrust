import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:mimotrust_controlled_content/models/content_context.dart';
import 'package:mimotrust_controlled_content/models/sandbox_content.dart';
import 'package:mimotrust_controlled_content/models/video_content.dart';
import 'package:mimotrust_controlled_content/services/content_grant_client.dart';
import 'package:mimotrust_controlled_content/services/context_dispatcher.dart';
import 'package:mimotrust_controlled_content/services/context_transport.dart';

void main() {
  test('dispatcher builds a deferred Context 2.2 candidate', () async {
    final observedAt = DateTime.utc(2026, 8, 1, 12);
    final content = _videoFixture();
    final reference = _reference(content);
    final client = _FakeGrantClient(
      ContentGrant(
        grantCode: 'one-time-code',
        expiresAt: observedAt.add(const Duration(minutes: 3)),
        audience: 'mimotrust_guardian_backend',
        scopes: const <String>['manifest:read', 'asset:read'],
        exchangeUrl: Uri.parse('http://127.0.0.1:8787/v1/grants/exchange'),
        contentReference: reference,
      ),
    );
    final transport = _RecordingTransport();
    final dispatcher = ContextDispatcher(
      client,
      eventIdGenerator: () => '2ce1c877-0245-4c31-9fd8-a39bd76900d1',
      transport: transport,
    );

    final context = await dispatcher.dispatchVideoContext(
      trigger: ContextTrigger.comment,
      content: content,
      viewState: MediaViewState(
        positionMs: 3500,
        durationMs: 22467,
        isPlaying: true,
      ),
      observedAt: observedAt,
    );
    final json = context.toJson();

    expect(transport.sent, hasLength(1));
    expect(transport.sent.single, same(context));
    expect(client.requested, isNull);
    expect(json.keys, <String>[
      'schema_version',
      'event_id',
      'trigger',
      'source_app',
      'provider',
      'content_ref',
      'content_access',
      'view_state',
      'observed_at',
    ]);
    expect(json['schema_version'], '2.2');
    expect(json['trigger'], 'comment');
    expect(json['source_app'], 'mimotrust_controlled_content');
    expect(json['provider'], <String, Object>{
      'provider_id': 'mimotrust_sandbox',
      'application_id': 'com.mimotrust.controlledcontent',
    });
    expect(json['content_ref'], reference.toJson());
    expect(json['content_access'], <String, Object>{'mode': 'deferred_grant'});
    expect(json['view_state'], <String, Object>{
      'position_ms': 3500,
      'duration_ms': 22467,
      'is_playing': true,
    });
    expect(json['observed_at'], '2026-08-01T12:00:00.000Z');

    final encoded = context.toJsonString();
    expect(utf8.encode(encoded).length, lessThan(32 * 1024));
    expect(encoded, isNot(contains('comment_body')));
    expect(encoded, isNot(contains('contact')));
    expect(encoded, isNot(contains('cookie')));
  });

  test('guardian request reuses request id and obtains a fresh grant', () async {
    final content = _videoFixture();
    final observedAt = DateTime.utc(2026, 8, 1, 12);
    final client = _FakeGrantClient(
      ContentGrant(
        grantCode: 'fresh-code',
        expiresAt: observedAt.add(const Duration(minutes: 3)),
        audience: 'mimotrust_guardian_backend',
        scopes: const <String>['manifest:read', 'asset:read'],
        exchangeUrl: Uri.parse('http://127.0.0.1:8787/v1/grants/exchange'),
        contentReference: _reference(content),
      ),
    );
    final transport = _RecordingTransport();
    final dispatcher = ContextDispatcher(client, transport: transport);
    const requestId = '2ce1c877-0245-4c31-9fd8-a39bd76900d1';

    final context = await dispatcher.dispatchGuardianRequest(
      requestId: requestId,
      content: content,
      viewState: MediaViewState(
        positionMs: 3500,
        durationMs: 22467,
        isPlaying: true,
      ),
      observedAt: observedAt,
    );

    expect(context.eventId, requestId);
    expect(context.trigger, ContextTrigger.guardianRequest);
    expect(client.requested?.toJson(), _reference(content).toJson());
    expect(
      context.toJson()['content_access'],
      containsPair('mode', 'grant_exchange'),
    );
    expect(transport.sent.single, same(context));
  });

  test('share uses the same dispatcher and a distinct event id', () async {
    final content = _videoFixture();
    final observedAt = DateTime.utc(2026, 8, 1, 12);
    final client = _FakeGrantClient(
      ContentGrant(
        grantCode: 'share-grant',
        expiresAt: observedAt.add(const Duration(minutes: 3)),
        audience: 'mimotrust_guardian_backend',
        scopes: const <String>['manifest:read', 'asset:read'],
        exchangeUrl: Uri.parse('http://127.0.0.1:8787/v1/grants/exchange'),
        contentReference: _reference(content),
      ),
    );
    final ids = <String>[
      '2ce1c877-0245-4c31-9fd8-a39bd76900d1',
      '8f052041-20f1-4a38-82be-5663dad7787e',
    ].iterator;
    final dispatcher = ContextDispatcher(
      client,
      transport: _RecordingTransport(),
      eventIdGenerator: () {
        ids.moveNext();
        return ids.current;
      },
    );
    final viewState = MediaViewState(
      positionMs: 1000,
      durationMs: 22467,
      isPlaying: false,
    );

    final comment = await dispatcher.dispatchVideoContext(
      trigger: ContextTrigger.comment,
      content: content,
      viewState: viewState,
      observedAt: observedAt,
    );
    final share = await dispatcher.dispatchVideoContext(
      trigger: ContextTrigger.share,
      content: content,
      viewState: viewState,
      observedAt: observedAt,
    );

    expect(comment.eventId, isNot(share.eventId));
    expect(share.toJson()['trigger'], 'share');
  });

  test('guardian request preserves article reading state', () async {
    final content = _articleFixture();
    final reference = ContentReference(
      contentType: content.contentType,
      contentId: content.id,
      contentVersion: content.version,
      contentHash: content.hash,
      canonicalUrl: content.canonicalUrl,
    );
    final observedAt = DateTime.utc(2026, 8, 2, 12);
    final client = _FakeGrantClient(
      ContentGrant(
        grantCode: 'article-code',
        expiresAt: observedAt.add(const Duration(minutes: 3)),
        audience: 'mimotrust_guardian_backend',
        scopes: const <String>['manifest:read', 'asset:read'],
        exchangeUrl: Uri.parse('http://127.0.0.1:8787/v1/grants/exchange'),
        contentReference: reference,
      ),
    );
    final transport = _RecordingTransport();
    final dispatcher = ContextDispatcher(client, transport: transport);

    final context = await dispatcher.dispatchGuardianRequest(
      requestId: '8f052041-20f1-4a38-82be-5663dad7787e',
      content: content,
      viewState: ReadingViewState(scrollRatio: 0.6, blockIndex: 3),
      observedAt: observedAt,
    );

    expect(context.toJson()['content_ref'], reference.toJson());
    expect(context.toJson()['view_state'], <String, Object>{
      'scroll_ratio': 0.6,
      'block_index': 3,
    });
    expect(client.requested?.contentType, 'article');
  });

  test('media view state rejects an out-of-range position', () {
    expect(
      () =>
          MediaViewState(positionMs: 22468, durationMs: 22467, isPlaying: true),
      throwsArgumentError,
    );
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
  _FakeGrantClient(this.grant);

  final ContentGrant grant;
  ContentReference? requested;

  @override
  Future<ContentGrant> issueGrant(ContentReference expectedContent) async {
    requested = expectedContent;
    return grant;
  }

  @override
  void close() {}
}

ContentReference _reference(VideoContent content) {
  return ContentReference(
    contentType: 'video',
    contentId: content.id,
    contentVersion: content.version,
    contentHash: content.hash,
    canonicalUrl: content.canonicalUrl,
  );
}

VideoContent _videoFixture() {
  return VideoContent(
    id: 'video-001',
    version: 'v1',
    hash: '0f6c57d2f3f2772a3abfde87b52123c45228a420e40cada19035dd26afa2f734',
    title: '测试视频',
    author: 'MiMoTrust',
    publishedAt: '2026-08-01T00:00:00+08:00',
    canonicalUrl: Uri.parse(
      'https://sandbox.mimotrust.local/content/video-001',
    ),
    videoUrl: Uri.parse('https://example.test/video.mp4'),
    coverAssetPath: 'assets/images/video-001-cover.png',
    duration: const Duration(milliseconds: 22467),
    width: 720,
    height: 1280,
  );
}

ArticleContent _articleFixture() {
  return ArticleContent(
    id: 'article-001',
    version: 'v1',
    hash: List<String>.filled(64, 'a').join(),
    title: '测试文章',
    author: 'MiMoTrust',
    publishedAt: '2026-08-02T00:00:00+08:00',
    canonicalUrl: Uri.parse(
      'https://sandbox.mimotrust.local/content/article-001',
    ),
    assets: const <ContentAsset>[],
    displayMetrics: const ContentDisplayMetrics.zero(),
    bodyUrl: Uri.parse('https://example.test/article.txt'),
    bodyMimeType: 'text/plain',
  );
}
