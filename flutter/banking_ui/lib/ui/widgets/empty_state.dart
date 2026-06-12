import 'package:flutter/material.dart';

import '../theme.dart';

/// Shown when the chat has no messages yet.
/// Displays quick-start suggestion chips.
class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.onSuggestionTap});

  final void Function(String suggestion) onSuggestionTap;

  static const _suggestions = [
    'Mera balance kya hai?',
    "Show this month's statement",
    'Open a Fixed Deposit',
    'Transfer ₹2000 to Rahul',
    'KYC documents kya chahiye?',
  ];

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: BankingTheme.brandPrimary.withValues(alpha: 0.08),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.account_balance_rounded,
                size: 36,
                color: BankingTheme.brandPrimary,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Banking Assistant',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w700,
                    color: BankingTheme.contentPrimary,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              'Ask in English, Hindi or Hinglish',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: BankingTheme.contentSecondary,
                  ),
            ),
            const SizedBox(height: 28),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                for (final s in _suggestions)
                  ActionChip(
                    label: Text(s),
                    onPressed: () => onSuggestionTap(s),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
