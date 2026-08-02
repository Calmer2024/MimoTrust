import 'package:flutter/material.dart';

import '../models/sandbox_comment.dart';

class CommentsSheet extends StatefulWidget {
  const CommentsSheet({
    super.key,
    required this.presetComments,
    required this.localComments,
    required this.onCommentAdded,
    this.baseCount,
  });

  final List<SandboxComment> presetComments;
  final List<SandboxComment> localComments;
  final Future<void> Function(SandboxComment comment) onCommentAdded;
  final int? baseCount;

  @override
  State<CommentsSheet> createState() => _CommentsSheetState();
}

class _CommentsSheetState extends State<CommentsSheet> {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  late final List<SandboxComment> _localComments = <SandboxComment>[
    ...widget.localComments,
  ];
  bool _submitting = false;

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final body = _controller.text.trim();
    if (body.isEmpty || _submitting) {
      return;
    }
    final comment = SandboxComment(author: '我', body: body);
    setState(() {
      _submitting = true;
      _localComments.add(comment);
      _controller.clear();
    });
    try {
      await widget.onCommentAdded(comment);
    } finally {
      if (mounted) {
        setState(() {
          _submitting = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final comments = <SandboxComment>[
      ...widget.presetComments,
      ..._localComments,
    ];
    final viewInsets = MediaQuery.viewInsetsOf(context);
    final screenHeight = MediaQuery.sizeOf(context).height;
    final sheetHeight = (screenHeight * 0.7)
        .clamp(0.0, screenHeight - viewInsets.bottom)
        .toDouble();
    return AnimatedPadding(
      key: const Key('comments-sheet'),
      duration: const Duration(milliseconds: 160),
      curve: Curves.easeOut,
      padding: EdgeInsets.only(bottom: viewInsets.bottom),
      child: SizedBox(
        height: sheetHeight,
        child: Column(
          children: [
            _SheetHeader(
              title: '评论 ${widget.baseCount == null ? comments.length : widget.baseCount! + _localComments.length}',
            ),
            Expanded(
              child: comments.isEmpty
                  ? const Center(
                      child: Text(
                        '还没有评论',
                        style: TextStyle(color: Color(0xFFAAAAAA)),
                      ),
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                      itemCount: comments.length,
                      separatorBuilder: (context, index) =>
                          const Divider(height: 20, color: Color(0xFF2B2B2B)),
                      itemBuilder: (context, index) =>
                          _CommentRow(comment: comments[index]),
                    ),
            ),
            const Divider(height: 1, color: Color(0xFF303030)),
            SafeArea(
              top: false,
              minimum: const EdgeInsets.fromLTRB(12, 10, 8, 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Expanded(
                    child: TextField(
                      key: const Key('comment-input'),
                      controller: _controller,
                      focusNode: _focusNode,
                      minLines: 1,
                      maxLines: 3,
                      maxLength: 200,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _submit(),
                      decoration: const InputDecoration(
                        hintText: '写下本地评论',
                        counterText: '',
                        filled: true,
                        fillColor: Color(0xFF242424),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.all(Radius.circular(6)),
                          borderSide: BorderSide.none,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 6),
                  IconButton(
                    key: const Key('comment-submit'),
                    onPressed: _submitting ? null : _submit,
                    tooltip: '发布本地评论',
                    icon: const Icon(Icons.send_rounded),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SheetHeader extends StatelessWidget {
  const _SheetHeader({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 52,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Text(
            title,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
          ),
          const Align(
            alignment: Alignment.centerRight,
            child: Padding(
              padding: EdgeInsets.only(right: 8),
              child: CloseButton(),
            ),
          ),
        ],
      ),
    );
  }
}

class _CommentRow extends StatelessWidget {
  const _CommentRow({required this.comment});

  final SandboxComment comment;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        CircleAvatar(
          radius: 17,
          backgroundColor: const Color(0xFF3B3B3B),
          child: Text(comment.author.characters.first),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                comment.author,
                style: const TextStyle(color: Color(0xFFB8B8B8), fontSize: 12),
              ),
              const SizedBox(height: 3),
              Text(comment.body),
            ],
          ),
        ),
      ],
    );
  }
}
