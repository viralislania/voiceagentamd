import 'package:flutter/material.dart';
import 'package:genui/genui.dart';

import '../../logic/models.dart';
import '../../logic/chat_store.dart';
import '../theme.dart';

/// Renders a single [BankingMessage] in the chat list.
///
/// User messages are right-aligned navy bubbles.
/// Agent text messages are left-aligned light bubbles.
/// Agent surface messages render a genui [Surface].
class MessageTile extends StatelessWidget {
  const MessageTile(this.message, this.store, {super.key});

  final BankingMessage message;
  final ChatStore store;

  @override
  Widget build(BuildContext context) {
    if (message.hasSurface) {
      return _SurfaceTile(message.surfaceId!, store);
    }

    return _TextTile(message);
  }
}

class _SurfaceTile extends StatelessWidget {
  const _SurfaceTile(this.surfaceId, this.store);
  final String surfaceId;
  final ChatStore store;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Surface(
        surfaceContext:
            store.client.surfaceController.contextFor(surfaceId),
        defaultBuilder: (_) => const Padding(
          padding: EdgeInsets.all(24),
          child: Center(child: CircularProgressIndicator()),
        ),
      ),
    );
  }
}

class _TextTile extends StatelessWidget {
  const _TextTile(this.message);
  final BankingMessage message;

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;
    final text   = message.text ?? '';

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 3),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        padding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: isUser ? BankingTheme.userBubble : BankingTheme.agentBubble,
          borderRadius: BorderRadius.only(
            topLeft:     const Radius.circular(18),
            topRight:    const Radius.circular(18),
            bottomLeft:  Radius.circular(isUser ? 18 : 4),
            bottomRight: Radius.circular(isUser ? 4 : 18),
          ),
        ),
        child: Text(
          text,
          style: TextStyle(
            color: isUser ? Colors.white : BankingTheme.contentPrimary,
            fontSize: 15,
            height: 1.4,
          ),
        ),
      ),
    );
  }
}
