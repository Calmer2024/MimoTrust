import 'package:shared_preferences/shared_preferences.dart';

import '../models/sandbox_comment.dart';

abstract interface class InteractionStore {
  Future<bool> loadLiked(String contentId, String contentVersion);

  Future<void> setLiked(String contentId, String contentVersion, bool liked);

  Future<List<SandboxComment>> loadComments(
    String contentId,
    String contentVersion,
  );

  Future<void> addComment(
    String contentId,
    String contentVersion,
    SandboxComment comment,
  );
}

class SharedPreferencesInteractionStore implements InteractionStore {
  const SharedPreferencesInteractionStore();

  static String _key(String kind, String contentId, String contentVersion) {
    return 'mimotrust.interactions.$kind.$contentId.$contentVersion';
  }

  @override
  Future<bool> loadLiked(String contentId, String contentVersion) async {
    final preferences = await SharedPreferences.getInstance();
    return preferences.getBool(_key('liked', contentId, contentVersion)) ??
        false;
  }

  @override
  Future<void> setLiked(
    String contentId,
    String contentVersion,
    bool liked,
  ) async {
    final preferences = await SharedPreferences.getInstance();
    final stored = await preferences.setBool(
      _key('liked', contentId, contentVersion),
      liked,
    );
    if (!stored) {
      throw StateError('Could not persist like state.');
    }
  }

  @override
  Future<List<SandboxComment>> loadComments(
    String contentId,
    String contentVersion,
  ) async {
    final preferences = await SharedPreferences.getInstance();
    final encoded =
        preferences.getStringList(
          _key('comments', contentId, contentVersion),
        ) ??
        const <String>[];
    final comments = <SandboxComment>[];
    for (final item in encoded) {
      try {
        comments.add(SandboxComment.fromJsonString(item));
      } on FormatException {
        // Ignore malformed local state instead of making the content unusable.
      }
    }
    return comments;
  }

  @override
  Future<void> addComment(
    String contentId,
    String contentVersion,
    SandboxComment comment,
  ) async {
    final preferences = await SharedPreferences.getInstance();
    final key = _key('comments', contentId, contentVersion);
    final encoded = <String>[...?preferences.getStringList(key)];
    encoded.add(comment.toJsonString());
    final stored = await preferences.setStringList(key, encoded);
    if (!stored) {
      throw StateError('Could not persist comment.');
    }
  }
}
