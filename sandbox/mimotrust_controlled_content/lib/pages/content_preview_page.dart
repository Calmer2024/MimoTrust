import 'package:flutter/material.dart';

import '../models/sandbox_content.dart';

class ContentPreviewPage extends StatelessWidget {
  const ContentPreviewPage({
    super.key,
    required this.content,
    required this.onOpen,
  });

  final SandboxContent content;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return switch (content) {
      final ImageGalleryContent gallery => _GalleryPreview(
        content: gallery,
        onOpen: onOpen,
      ),
      final RichArticleContent article => _ReadingPreview(
        content: article,
        imageUrl: article.blocks
            .where((block) => block.asset != null)
            .firstOrNull
            ?.asset
            ?.sourceUrl,
        summary: article.blocks
            .where((block) => block.text != null)
            .firstOrNull
            ?.text,
        actionLabel: '阅读图文',
        onOpen: onOpen,
      ),
      final ArticleContent article => _ReadingPreview(
        content: article,
        actionLabel: '阅读全文',
        onOpen: onOpen,
      ),
      _ => const SizedBox.shrink(),
    };
  }
}

class _ReadingPreview extends StatelessWidget {
  const _ReadingPreview({
    required this.content,
    required this.actionLabel,
    required this.onOpen,
    this.imageUrl,
    this.summary,
  });

  final SandboxContent content;
  final String actionLabel;
  final VoidCallback onOpen;
  final Uri? imageUrl;
  final String? summary;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F5F6),
      body: InkWell(
        key: Key('open-content-${content.id}'),
        onTap: onOpen,
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(22, 76, 22, 34),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (imageUrl != null) ...[
                  Expanded(
                    flex: 5,
                    child: SizedBox.expand(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(6),
                        child: Image.network(
                          imageUrl.toString(),
                          fit: BoxFit.cover,
                          errorBuilder: _previewImageError,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),
                ] else
                  const Spacer(flex: 2),
                Text(
                  content.title,
                  maxLines: 4,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Color(0xFF16181B),
                    fontSize: 28,
                    height: 1.35,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 14),
                Text(
                  '${content.author}  ·  ${content.publishedAt.substring(0, 10)}',
                  style: const TextStyle(color: Color(0xFF686E75), fontSize: 14),
                ),
                if (summary case final String value) ...[
                  const SizedBox(height: 18),
                  Text(
                    value,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Color(0xFF454A50),
                      fontSize: 16,
                      height: 1.65,
                    ),
                  ),
                ],
                const Spacer(),
                Align(
                  alignment: Alignment.centerRight,
                  child: FilledButton.icon(
                    onPressed: onOpen,
                    icon: const Icon(Icons.menu_book_rounded),
                    label: Text(actionLabel),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _GalleryPreview extends StatelessWidget {
  const _GalleryPreview({required this.content, required this.onOpen});

  final ImageGalleryContent content;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: InkWell(
        key: Key('open-content-${content.id}'),
        onTap: onOpen,
        child: Stack(
          fit: StackFit.expand,
          children: [
            Image.network(
              content.images.first.sourceUrl.toString(),
              fit: BoxFit.contain,
              errorBuilder: _previewImageError,
            ),
            SafeArea(
              child: Align(
                alignment: Alignment.bottomLeft,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 20, 20, 34),
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      color: const Color(0xE6111111),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            content.title,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 19,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              Text(
                                content.author,
                                style: const TextStyle(color: Color(0xFFD7DADF)),
                              ),
                              const Spacer(),
                              const Icon(
                                Icons.photo_library_outlined,
                                color: Colors.white,
                                size: 18,
                              ),
                              const SizedBox(width: 6),
                              Text(
                                '${content.images.length}',
                                style: const TextStyle(color: Colors.white),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

Widget _previewImageError(
  BuildContext context,
  Object error,
  StackTrace? stackTrace,
) {
  return const ColoredBox(
    color: Color(0xFF272A2E),
    child: Center(
      child: Icon(Icons.broken_image_outlined, color: Colors.white54, size: 46),
    ),
  );
}
