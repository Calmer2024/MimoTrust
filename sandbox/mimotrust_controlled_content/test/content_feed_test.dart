import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mimotrust_controlled_content/models/sandbox_content.dart';
import 'package:mimotrust_controlled_content/services/content_repository.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('remote Feed discovers a newly published article', () async {
    final client = MockClient((request) async {
      expect(request.url.toString(), 'http://gateway.test/v1/feed');
      return http.Response(
        jsonEncode(<String, Object>{
          'registry_version': '1.0',
          'provider_id': 'mimotrust_sandbox',
          'updated_at': '2026-08-02T08:31:23Z',
          'contents': <Object>[
            <String, Object>{
              'content_id': 'broken-entry',
              'content_version': 'v1',
              'content_type': 'article',
              'display_order': 0,
              'display_metrics': _metrics,
              'manifest': <String, Object>{},
            },
            <String, Object>{
              'content_id': 'article-001',
              'content_version': 'v1',
              'content_type': 'article',
              'display_order': 3,
              'display_metrics': _metrics,
              'manifest': _articleManifest(),
            },
          ],
        }),
        200,
        headers: const <String, String>{
          'content-type': 'application/json; charset=utf-8',
        },
      );
    });
    final repository = ContentRepository(
      httpClient: client,
      gatewayBaseUrl: Uri.parse('http://gateway.test'),
    );

    final contents = await repository.loadRemoteFeed();

    expect(contents, hasLength(1));
    expect(contents.single, isA<ArticleContent>());
    final article = contents.single as ArticleContent;
    expect(article.id, 'article-001');
    expect(
      article.bodyUrl,
      Uri.parse('https://oss.example.test/article-body.txt'),
    );
  });

  test('remote Feed failure falls back to the three bundled videos', () async {
    final repository = ContentRepository(
      httpClient: MockClient((request) async => http.Response('unavailable', 503)),
      gatewayBaseUrl: Uri.parse('http://gateway.test'),
    );

    final contents = await repository.loadContentFeed();

    expect(contents.map((item) => item.id), <String>[
      'video-001',
      'video-002',
      'video-003',
    ]);
  });
}

const _metrics = <String, int>{
  'like_count': 0,
  'comment_count': 0,
  'share_count': 0,
};

Map<String, Object> _articleManifest() => <String, Object>{
  'manifest_version': '1.0',
  'provider': <String, String>{'provider_id': 'mimotrust_sandbox'},
  'content': <String, Object>{
    'content_type': 'article',
    'content_id': 'article-001',
    'content_version': 'v1',
    'content_hash': List<String>.filled(64, 'a').join(),
    'canonical_url': 'https://sandbox.mimotrust.local/content/article-001',
    'title': '测试文章',
    'author': '测试作者',
    'published_at': '2026-08-02T00:00:00+08:00',
    'body_asset_id': 'article-body',
    'asset_order': <String>['article-body'],
  },
  'assets': <Object>[
    <String, Object>{
      'asset_id': 'article-body',
      'role': 'analysis',
      'mime_type': 'text/plain',
      'source_url': 'https://oss.example.test/article-body.txt',
      'sha256': List<String>.filled(64, 'a').join(),
      'size_bytes': 128,
      'derivation': 'original',
      'order': 0,
    },
  ],
  'rights': <String, Object>{
    'purpose': <String>['fact_check'],
    'retention_seconds': 3600,
    'redistribution_allowed': false,
  },
  'sandbox': <String, Object>{
    'access_enforcement': 'mock_gateway_only',
    'development_asset': true,
  },
};
