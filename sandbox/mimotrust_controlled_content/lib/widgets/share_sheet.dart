import 'package:flutter/material.dart';

class SandboxContact {
  const SandboxContact({
    required this.name,
    required this.subtitle,
    required this.initial,
  });

  final String name;
  final String subtitle;
  final String initial;
}

const sandboxContacts = <SandboxContact>[
  SandboxContact(name: '项目讨论组', subtitle: '沙盒虚拟会话', initial: '项'),
  SandboxContact(name: '内容评审组', subtitle: '沙盒虚拟会话', initial: '审'),
  SandboxContact(name: '演示联系人', subtitle: '沙盒虚拟联系人', initial: '演'),
  SandboxContact(name: '收藏助手', subtitle: '沙盒虚拟联系人', initial: '收'),
];

class ShareSheet extends StatefulWidget {
  const ShareSheet({super.key, this.contacts = sandboxContacts});

  final List<SandboxContact> contacts;

  @override
  State<ShareSheet> createState() => _ShareSheetState();
}

class _ShareSheetState extends State<ShareSheet> {
  SandboxContact? _selected;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      key: const Key('share-sheet'),
      top: false,
      minimum: const EdgeInsets.fromLTRB(16, 4, 16, 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            height: 48,
            child: Stack(
              alignment: Alignment.center,
              children: [
                const Text(
                  '转发到',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                ),
                const Align(
                  alignment: Alignment.centerRight,
                  child: CloseButton(),
                ),
              ],
            ),
          ),
          if (widget.contacts.isEmpty)
            const SizedBox(
              height: 160,
              child: Center(
                child: Text(
                  '暂无虚拟联系人',
                  style: TextStyle(color: Color(0xFFAAAAAA)),
                ),
              ),
            )
          else
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              padding: const EdgeInsets.symmetric(vertical: 8),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 4,
                mainAxisExtent: 112,
                crossAxisSpacing: 8,
              ),
              itemCount: widget.contacts.length,
              itemBuilder: (context, index) {
                final contact = widget.contacts[index];
                final selected = identical(_selected, contact);
                return InkWell(
                  key: Key('share-contact-$index'),
                  borderRadius: BorderRadius.circular(6),
                  onTap: () {
                    setState(() {
                      _selected = contact;
                    });
                  },
                  child: Column(
                    children: [
                      CircleAvatar(
                        radius: 25,
                        backgroundColor: selected
                            ? Theme.of(context).colorScheme.primary
                            : const Color(0xFF353535),
                        child: Text(
                          contact.initial,
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                      ),
                      const SizedBox(height: 7),
                      Text(
                        contact.name,
                        maxLines: 1,
                        textAlign: TextAlign.center,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 12),
                      ),
                      Text(
                        contact.subtitle,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Color(0xFF9E9E9E),
                          fontSize: 9,
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              key: const Key('share-submit'),
              onPressed: _selected == null
                  ? null
                  : () => Navigator.of(context).pop(_selected),
              icon: const Icon(Icons.send_rounded),
              label: const Text('模拟发送'),
            ),
          ),
        ],
      ),
    );
  }
}
