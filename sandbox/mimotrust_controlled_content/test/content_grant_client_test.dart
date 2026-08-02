import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mimotrust_controlled_content/models/content_context.dart';
import 'package:mimotrust_controlled_content/services/content_grant_client.dart';

void main() {
  test(
    'grant client sends the fixed request and validates the response',
    () async {
      late http.Request captured;
      final client = GatewayContentGrantClient(
        baseUrl: Uri.parse('http://127.0.0.1:8787'),
        httpClient: MockClient((request) async {
          captured = request;
          return http.Response(jsonEncode(_grantResponse()), 201);
        }),
      );

      final grant = await client.issueGrant(_reference());
      final requestJson = jsonDecode(captured.body) as Map<String, dynamic>;

      expect(captured.method, 'POST');
      expect(
        captured.url.toString(),
        'http://127.0.0.1:8787/v1/context-grants',
      );
      expect(requestJson, <String, Object>{
        'content_id': 'video-001',
        'content_version': 'v1',
        'audience': 'mimotrust_guardian_backend',
        'scopes': <String>['manifest:read', 'asset:read'],
      });
      expect(grant.grantCode, 'one-time-code');
      expect(grant.contentReference.contentHash, _reference().contentHash);
    },
  );

  test('grant client rejects a mismatched gateway content reference', () async {
    final response = _grantResponse();
    final contentRef = response['content_ref'] as Map<String, Object>;
    contentRef['content_hash'] = List<String>.filled(64, 'a').join();
    final client = GatewayContentGrantClient(
      baseUrl: Uri.parse('http://127.0.0.1:8787'),
      httpClient: MockClient(
        (request) async => http.Response(jsonEncode(response), 201),
      ),
    );

    expect(
      () => client.issueGrant(_reference()),
      throwsA(
        isA<GatewayGrantException>().having(
          (error) => error.code,
          'code',
          'INVALID_GATEWAY_RESPONSE',
        ),
      ),
    );
  });

  test(
    'grant client maps non-success status without exposing its body',
    () async {
      final client = GatewayContentGrantClient(
        baseUrl: Uri.parse('http://127.0.0.1:8787'),
        httpClient: MockClient(
          (request) async => http.Response(
            '{"error":{"code":"CONTENT_UNAVAILABLE","message":"secret"}}',
            404,
          ),
        ),
      );

      expect(
        () => client.issueGrant(_reference()),
        throwsA(
          isA<GatewayGrantException>().having(
            (error) => error.code,
            'code',
            'GATEWAY_HTTP_404',
          ),
        ),
      );
    },
  );
}

ContentReference _reference() {
  return ContentReference(
    contentType: 'video',
    contentId: 'video-001',
    contentVersion: 'v1',
    contentHash:
        '0f6c57d2f3f2772a3abfde87b52123c45228a420e40cada19035dd26afa2f734',
    canonicalUrl: Uri.parse(
      'https://sandbox.mimotrust.local/content/video-001',
    ),
  );
}

Map<String, Object> _grantResponse() {
  return <String, Object>{
    'grant_code': 'one-time-code',
    'expires_at': '2026-08-01T12:03:00Z',
    'audience': 'mimotrust_guardian_backend',
    'scopes': <String>['manifest:read', 'asset:read'],
    'exchange_url': 'http://127.0.0.1:8787/v1/grants/exchange',
    'content_ref': <String, Object>{
      'content_type': 'video',
      'content_id': 'video-001',
      'content_version': 'v1',
      'content_hash':
          '0f6c57d2f3f2772a3abfde87b52123c45228a420e40cada19035dd26afa2f734',
      'canonical_url': 'https://sandbox.mimotrust.local/content/video-001',
    },
  };
}
