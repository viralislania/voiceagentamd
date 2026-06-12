import 'package:flutter/material.dart';

import '../theme.dart';

/// Bottom input bar with text field + send button.
class InputBar extends StatelessWidget {
  const InputBar({
    super.key,
    required this.controller,
    required this.isProcessing,
    required this.onSend,
  });

  final TextEditingController controller;
  final bool isProcessing;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 6, 8, 12),
      decoration: BoxDecoration(
        color: BankingTheme.surfaceCard,
        border: const Border(
          top: BorderSide(color: BankingTheme.borderSubtle),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 8,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                enabled: !isProcessing,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => onSend(),
                minLines: 1,
                maxLines: 4,
                decoration: const InputDecoration(
                  hintText: 'Balance, transfer, FD — ask anything…',
                ),
              ),
            ),
            const SizedBox(width: 8),
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 200),
              child: isProcessing
                  ? const Padding(
                      padding: EdgeInsets.all(12),
                      child: SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          color: BankingTheme.brandPrimary,
                        ),
                      ),
                    )
                  : IconButton.filled(
                      onPressed: onSend,
                      style: IconButton.styleFrom(
                        backgroundColor: BankingTheme.brandPrimary,
                        foregroundColor: Colors.white,
                      ),
                      icon: const Icon(Icons.send_rounded),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
