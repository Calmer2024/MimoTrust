import 'dart:convert';

class SandboxComment {
  const SandboxComment({required this.author, required this.body});

  final String author;
  final String body;

  String toJsonString() {
    return jsonEncode(<String, String>{'author': author, 'body': body});
  }

  factory SandboxComment.fromJsonString(String source) {
    final Object? decoded = jsonDecode(source);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Comment must be an object.');
    }
    final author = decoded['author'];
    final body = decoded['body'];
    if (author is! String || author.trim().isEmpty) {
      throw const FormatException('Comment author must not be empty.');
    }
    if (body is! String || body.trim().isEmpty) {
      throw const FormatException('Comment body must not be empty.');
    }
    return SandboxComment(author: author.trim(), body: body.trim());
  }
}
