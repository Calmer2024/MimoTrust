import 'package:flutter_test/flutter_test.dart';
import 'package:mimotrust_controlled_content/models/sandbox_content.dart';

void main() {
  test('audio Manifest parses playback duration and URL', () {
    final content = SandboxContent.fromManifest(
      _manifest(
        type: 'audio',
        id: 'audio-001',
        hash: _hash('a'),
        contentExtra: const <String, Object>{
          'asset_order': <String>['audio-main'],
        },
        assets: <Map<String, Object>>[
          _asset(
            id: 'audio-main',
            mime: 'audio/mpeg',
            hash: _hash('a'),
            extra: const <String, Object>{'duration_ms': 180000},
          ),
        ],
      ),
      useNetworkAssets: true,
    );

    expect(content, isA<AudioContent>());
    expect((content as AudioContent).duration, const Duration(minutes: 3));
  });

  test('rich article Manifest preserves ordered text and image blocks', () {
    final content = SandboxContent.fromManifest(
      _manifest(
        type: 'rich_article',
        id: 'rich-001',
        hash: _hash('b'),
        contentExtra: const <String, Object>{
          'asset_order': <String>['image-001'],
          'blocks': <Object>[
            <String, Object>{
              'block_index': 0,
              'block_type': 'text',
              'text': '第一段',
            },
            <String, Object>{
              'block_index': 1,
              'block_type': 'image',
              'asset_id': 'image-001',
            },
          ],
        },
        assets: <Map<String, Object>>[
          _asset(id: 'image-001', mime: 'image/png', hash: _hash('c')),
        ],
      ),
    );

    expect(content, isA<RichArticleContent>());
    final rich = content as RichArticleContent;
    expect(rich.blocks.map((block) => block.type), <String>['text', 'image']);
    expect(rich.blocks.last.asset?.id, 'image-001');
  });

  test('image gallery uses Manifest asset order', () {
    final content = SandboxContent.fromManifest(
      _manifest(
        type: 'image_gallery',
        id: 'gallery-001',
        hash: _hash('d'),
        contentExtra: const <String, Object>{
          'asset_order': <String>['image-002', 'image-001'],
        },
        assets: <Map<String, Object>>[
          _asset(id: 'image-001', mime: 'image/png', hash: _hash('e')),
          _asset(id: 'image-002', mime: 'image/jpeg', hash: _hash('f')),
        ],
      ),
    );

    expect(content, isA<ImageGalleryContent>());
    expect(
      (content as ImageGalleryContent).images.map((asset) => asset.id),
      <String>['image-002', 'image-001'],
    );
  });
}

Map<String, dynamic> _manifest({
  required String type,
  required String id,
  required String hash,
  required Map<String, Object> contentExtra,
  required List<Map<String, Object>> assets,
}) => <String, dynamic>{
  'manifest_version': '1.0',
  'provider': <String, Object>{'provider_id': 'mimotrust_sandbox'},
  'content': <String, Object>{
    'content_type': type,
    'content_id': id,
    'content_version': 'v1',
    'content_hash': hash,
    'canonical_url': 'https://sandbox.mimotrust.local/content/$id',
    'title': '测试内容',
    'author': '测试作者',
    'published_at': '2026-08-02T00:00:00+08:00',
    ...contentExtra,
  },
  'assets': assets,
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

Map<String, Object> _asset({
  required String id,
  required String mime,
  required String hash,
  Map<String, Object> extra = const <String, Object>{},
}) => <String, Object>{
  'asset_id': id,
  'role': 'analysis',
  'mime_type': mime,
  'source_url': 'https://oss.example.test/$id',
  'sha256': hash,
  'size_bytes': 128,
  'derivation': 'original',
  ...extra,
};

String _hash(String character) => List<String>.filled(64, character).join();
