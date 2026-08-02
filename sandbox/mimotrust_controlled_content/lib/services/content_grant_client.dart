import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/content_context.dart';

abstract interface class ContentGrantClient {
  Future<ContentGrant> issueGrant(ContentReference expectedContent);

  void close();
}

class GatewayGrantException implements Exception {
  const GatewayGrantException(this.code);

  final String code;

  @override
  String toString() => 'GatewayGrantException($code)';
}

class GatewayContentGrantClient implements ContentGrantClient {
  GatewayContentGrantClient({
    required this.baseUrl,
    http.Client? httpClient,
    this.timeout = const Duration(seconds: 2),
  }) : _httpClient = httpClient ?? http.Client();

  static const audience = 'mimotrust_guardian_backend';
  static const scopes = <String>['manifest:read', 'asset:read'];

  final Uri baseUrl;
  final Duration timeout;
  final http.Client _httpClient;

  @override
  Future<ContentGrant> issueGrant(ContentReference expectedContent) async {
    final endpoint = baseUrl.resolve('/v1/context-grants');
    late final http.Response response;
    try {
      response = await _httpClient
          .post(
            endpoint,
            headers: const <String, String>{
              'Content-Type': 'application/json; charset=utf-8',
            },
            body: jsonEncode(<String, Object>{
              'content_id': expectedContent.contentId,
              'content_version': expectedContent.contentVersion,
              'audience': audience,
              'scopes': scopes,
            }),
          )
          .timeout(timeout);
    } on TimeoutException {
      throw const GatewayGrantException('GATEWAY_TIMEOUT');
    } on http.ClientException {
      throw const GatewayGrantException('GATEWAY_UNAVAILABLE');
    }

    if (response.statusCode != 201) {
      throw GatewayGrantException('GATEWAY_HTTP_${response.statusCode}');
    }

    try {
      final Object? decoded = jsonDecode(response.body);
      final root = _object(decoded, 'response');
      _exactKeys(root, const <String>{
        'grant_code',
        'expires_at',
        'audience',
        'scopes',
        'exchange_url',
        'content_ref',
      });
      final returnedReference = _contentReference(root['content_ref']);
      if (!_sameContent(returnedReference, expectedContent)) {
        throw const FormatException('Gateway content_ref mismatch.');
      }
      final expiresAt = DateTime.parse(_string(root['expires_at']));
      final rawScopes = root['scopes'];
      if (rawScopes is! List || rawScopes.any((item) => item is! String)) {
        throw const FormatException('Invalid grant scopes.');
      }
      return ContentGrant(
        grantCode: _string(root['grant_code']),
        expiresAt: expiresAt,
        audience: _string(root['audience']),
        scopes: rawScopes.cast<String>(),
        exchangeUrl: Uri.parse(_string(root['exchange_url'])),
        contentReference: returnedReference,
      );
    } on FormatException {
      throw const GatewayGrantException('INVALID_GATEWAY_RESPONSE');
    } on ArgumentError {
      throw const GatewayGrantException('INVALID_GATEWAY_RESPONSE');
    }
  }

  @override
  void close() {
    _httpClient.close();
  }

  static ContentReference _contentReference(Object? value) {
    final map = _object(value, 'content_ref');
    _exactKeys(map, const <String>{
      'content_type',
      'content_id',
      'content_version',
      'content_hash',
      'canonical_url',
    });
    return ContentReference(
      contentType: _string(map['content_type']),
      contentId: _string(map['content_id']),
      contentVersion: _string(map['content_version']),
      contentHash: _string(map['content_hash']),
      canonicalUrl: Uri.parse(_string(map['canonical_url'])),
    );
  }

  static Map<String, dynamic> _object(Object? value, String name) {
    if (value is! Map<String, dynamic>) {
      throw FormatException('$name must be an object.');
    }
    return value;
  }

  static String _string(Object? value) {
    if (value is! String || value.isEmpty) {
      throw const FormatException('Expected a non-empty string.');
    }
    return value;
  }

  static void _exactKeys(Map<String, dynamic> value, Set<String> expected) {
    if (value.keys.toSet().difference(expected).isNotEmpty ||
        expected.difference(value.keys.toSet()).isNotEmpty) {
      throw const FormatException('Unexpected response fields.');
    }
  }

  static bool _sameContent(ContentReference left, ContentReference right) {
    return left.contentType == right.contentType &&
        left.contentId == right.contentId &&
        left.contentVersion == right.contentVersion &&
        left.contentHash == right.contentHash &&
        left.canonicalUrl == right.canonicalUrl;
  }
}
