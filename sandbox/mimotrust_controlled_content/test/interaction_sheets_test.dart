import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mimotrust_controlled_content/models/sandbox_comment.dart';
import 'package:mimotrust_controlled_content/widgets/comments_sheet.dart';
import 'package:mimotrust_controlled_content/widgets/share_sheet.dart';

void main() {
  testWidgets('comments sheet shows preset, local, and newly added comments', (
    tester,
  ) async {
    SandboxComment? saved;
    await tester.pumpWidget(
      _TestApp(
        child: CommentsSheet(
          presetComments: const <SandboxComment>[
            SandboxComment(author: '访客', body: '预置评论'),
          ],
          localComments: const <SandboxComment>[
            SandboxComment(author: '我', body: '已有本地评论'),
          ],
          onCommentAdded: (comment) async {
            saved = comment;
          },
        ),
      ),
    );

    expect(find.text('预置评论'), findsOneWidget);
    expect(find.text('已有本地评论'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('comment-input')), '新增本地评论');
    await tester.tap(find.byKey(const Key('comment-submit')));
    await tester.pumpAndSettle();

    expect(find.text('新增本地评论'), findsOneWidget);
    expect(saved?.author, '我');
    expect(saved?.body, '新增本地评论');
  });

  testWidgets('comments sheet has an explicit empty state', (tester) async {
    await tester.pumpWidget(
      _TestApp(
        child: CommentsSheet(
          presetComments: const <SandboxComment>[],
          localComments: const <SandboxComment>[],
          onCommentAdded: (_) async {},
        ),
      ),
    );

    expect(find.text('还没有评论'), findsOneWidget);
  });

  testWidgets('share sheet returns only a selected virtual contact', (
    tester,
  ) async {
    SandboxContact? selected;
    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark(useMaterial3: true),
        home: Scaffold(
          body: Builder(
            builder: (context) => FilledButton(
              onPressed: () async {
                selected = await showModalBottomSheet<SandboxContact>(
                  context: context,
                  builder: (context) => const ShareSheet(),
                );
              },
              child: const Text('打开'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('打开'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('share-sheet')), findsOneWidget);
    expect(find.text('沙盒虚拟联系人'), findsNWidgets(2));

    await tester.tap(find.byKey(const Key('share-contact-2')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('share-submit')));
    await tester.pumpAndSettle();

    expect(selected?.name, '演示联系人');
  });

  testWidgets('share sheet has an explicit empty state', (tester) async {
    await tester.pumpWidget(
      const _TestApp(child: ShareSheet(contacts: <SandboxContact>[])),
    );

    expect(find.text('暂无虚拟联系人'), findsOneWidget);
  });
}

class _TestApp extends StatelessWidget {
  const _TestApp({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      theme: ThemeData.dark(useMaterial3: true),
      home: Scaffold(body: child),
    );
  }
}
