import 'package:flutter_test/flutter_test.dart';
import 'package:mimotrust_controlled_content/models/sandbox_comment.dart';
import 'package:mimotrust_controlled_content/services/local_interaction_store.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  test('like state persists and is isolated by content version', () async {
    const store = SharedPreferencesInteractionStore();

    expect(await store.loadLiked('video-001', 'v1'), isFalse);
    await store.setLiked('video-001', 'v1', true);

    expect(await store.loadLiked('video-001', 'v1'), isTrue);
    expect(await store.loadLiked('video-001', 'v2'), isFalse);
  });

  test('local comments persist in insertion order', () async {
    const store = SharedPreferencesInteractionStore();
    const first = SandboxComment(author: '我', body: '第一条本地评论');
    const second = SandboxComment(author: '我', body: '第二条本地评论');

    await store.addComment('video-001', 'v1', first);
    await store.addComment('video-001', 'v1', second);
    final comments = await store.loadComments('video-001', 'v1');

    expect(comments, hasLength(2));
    expect(comments[0].body, first.body);
    expect(comments[1].body, second.body);
  });

  test('malformed local comments are ignored', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{
      'mimotrust.interactions.comments.video-001.v1': <String>[
        '{not-json',
        const SandboxComment(author: '我', body: '有效评论').toJsonString(),
      ],
    });
    const store = SharedPreferencesInteractionStore();

    final comments = await store.loadComments('video-001', 'v1');

    expect(comments, hasLength(1));
    expect(comments.single.body, '有效评论');
  });
}
