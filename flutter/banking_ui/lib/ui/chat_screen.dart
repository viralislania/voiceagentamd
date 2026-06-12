import 'package:flutter/material.dart';
import 'package:flutter_mobx/flutter_mobx.dart';

import '../logic/chat_store.dart';
import 'theme.dart';
import 'widgets/empty_state.dart';
import 'widgets/input_bar.dart';
import 'widgets/message_tile.dart';

/// Main chat screen.
///
/// [contextLabel] is shown as a pill in the app-bar (e.g. "Spends", "Transfer money").
/// [initialMessage] is auto-sent on first load (e.g. from a Home screen quick-action tap).
/// [accountLabel] is the account display name shown in the header (e.g. "Savings ••1234").
class ChatScreen extends StatefulWidget {
  const ChatScreen({
    super.key,
    this.contextLabel,
    this.initialMessage,
    this.accountLabel,
    this.onConversationStarted,
  });

  final String? contextLabel;
  final String? initialMessage;
  final String? accountLabel;
  /// Called once with the first user message; use to persist history.
  final void Function(String message)? onConversationStarted;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  late final ChatStore _store;
  final _textController   = TextEditingController();
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _store = ChatStore(onConversationStarted: widget.onConversationStarted);
    _store.messages.observe((_) => _scrollToBottom());

    if (widget.initialMessage != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _store.sendMessage(widget.initialMessage!);
      });
    }
  }

  @override
  void dispose() {
    _store.dispose();
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send() async {
    final text = _textController.text.trim();
    if (text.isEmpty) return;
    _textController.clear();
    await _store.sendMessage(text);
  }

  void _sendSuggestion(String text) {
    _textController.text = text;
    _send();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            const Row(
              children: [
                Icon(Icons.account_balance_rounded, size: 18),
                SizedBox(width: 6),
                Text('Banking Assistant'),
              ],
            ),
            if (widget.contextLabel != null || widget.accountLabel != null)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Row(
                  children: [
                    if (widget.contextLabel != null)
                      _ContextPill(label: widget.contextLabel!),
                    if (widget.contextLabel != null && widget.accountLabel != null)
                      const SizedBox(width: 6),
                    if (widget.accountLabel != null)
                      Text(
                        widget.accountLabel!,
                        style: const TextStyle(
                          fontSize: 11,
                          color: BankingTheme.contentSecondary,
                          fontWeight: FontWeight.w400,
                        ),
                      ),
                  ],
                ),
              ),
          ],
        ),
        actions: [
          Observer(
            builder: (_) => _store.isProcessing
                ? const Padding(
                    padding: EdgeInsets.only(right: 16),
                    child: Center(
                      child: SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
                  )
                : const SizedBox.shrink(),
          ),
        ],
      ),
      body: Column(
        children: [
          Observer(
            builder: (_) => _store.errorMessage != null
                ? _ErrorBanner(
                    message: _store.errorMessage!,
                    onDismiss: _store.clearError,
                  )
                : const SizedBox.shrink(),
          ),
          Expanded(
            child: Observer(
              builder: (_) => _store.messages.isEmpty
                  ? EmptyState(onSuggestionTap: _sendSuggestion)
                  : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                      itemCount: _store.messages.length,
                      itemBuilder: (_, i) => MessageTile(
                        _store.messages[i],
                        _store,
                      ),
                    ),
            ),
          ),
          Observer(
            builder: (_) => InputBar(
              controller: _textController,
              isProcessing: _store.isProcessing,
              onSend: _send,
            ),
          ),
        ],
      ),
    );
  }
}

// ── Context pill ──────────────────────────────────────────────────────────────

class _ContextPill extends StatelessWidget {
  const _ContextPill({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: BankingTheme.surfaceSubtle,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        label,
        style: const TextStyle(
          fontSize: 11, fontWeight: FontWeight.w600,
          color: BankingTheme.brandPrimary,
        ),
      ),
    );
  }
}

// ── Error banner ──────────────────────────────────────────────────────────────

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message, required this.onDismiss});

  final String message;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    return MaterialBanner(
      backgroundColor: BankingTheme.statusDanger.withValues(alpha: 0.1),
      leading: const Icon(Icons.error_outline, color: BankingTheme.statusDanger),
      content: Text(
        message,
        style: const TextStyle(color: BankingTheme.statusDanger, fontSize: 13),
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
      actions: [
        TextButton(
          onPressed: onDismiss,
          child: const Text('Dismiss'),
        ),
      ],
    );
  }
}
