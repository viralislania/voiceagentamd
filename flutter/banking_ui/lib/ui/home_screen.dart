import 'package:flutter/material.dart';
import 'package:flutter_mobx/flutter_mobx.dart';

import '../logic/history_service.dart';
import '../logic/home_store.dart';
import '../logic/models.dart';
import 'chat_screen.dart';
import 'theme.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late final HomeStore _store;
  final _history = HistoryService();
  List<ConversationRecord> _records = [];

  @override
  void initState() {
    super.initState();
    _store = HomeStore();
    _store.load();
    _loadHistory();
  }

  @override
  void dispose() {
    _store.clearError();
    super.dispose();
  }

  Future<void> _loadHistory() async {
    final records = await _history.load();
    if (mounted) setState(() => _records = records);
  }

  void _openChat({String? message, String? contextLabel}) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => ChatScreen(
        initialMessage:        message,
        contextLabel:          contextLabel,
        accountLabel:          _store.account?.displayLabel,
        onConversationStarted: (firstMsg) => _saveRecord(firstMsg, contextLabel),
      ),
    ));
  }

  Future<void> _saveRecord(String firstMsg, String? contextLabel) async {
    final record = ConversationRecord(
      title:          firstMsg.length > 50 ? '${firstMsg.substring(0, 47)}…' : firstMsg,
      subtitle:       contextLabel ?? 'Chat',
      timestamp:      DateTime.now(),
      initialMessage: firstMsg,
      contextLabel:   contextLabel,
    );
    await _history.add(record);
    await _loadHistory();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: BankingTheme.surfaceBackground,
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _openChat(),
        backgroundColor: BankingTheme.brandPrimary,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.chat_bubble_outline_rounded),
        label: const Text('Ask anything'),
      ),
      body: SafeArea(
        child: Observer(
          builder: (_) {
            if (_store.isLoading) {
              return const Center(child: CircularProgressIndicator());
            }
            return CustomScrollView(
              slivers: [
                SliverToBoxAdapter(child: _GreetingCard(store: _store)),
                SliverToBoxAdapter(child: _BalanceCard(store: _store, onTap: _openChat)),
                SliverToBoxAdapter(child: _QuickActions(onTap: _openChat)),
                if (_records.isNotEmpty) ...[
                  SliverToBoxAdapter(child: _RecentHeader()),
                  SliverList(
                    delegate: SliverChildBuilderDelegate(
                      (_, i) => _HistoryTile(_records[i], onTap: _openChat),
                      childCount: _records.length,
                    ),
                  ),
                ],
                const SliverToBoxAdapter(child: SizedBox(height: 96)),
              ],
            );
          },
        ),
      ),
    );
  }
}

// ── Greeting card ─────────────────────────────────────────────────────────────

class _GreetingCard extends StatelessWidget {
  const _GreetingCard({required this.store});
  final HomeStore store;

  @override
  Widget build(BuildContext context) {
    return Observer(
      builder: (_) {
        final name     = store.profile?.firstName ?? 'there';
        final initials = store.profile?.avatarInitials ?? '??';
        return Container(
          margin: const EdgeInsets.fromLTRB(16, 16, 16, 0),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
          decoration: BoxDecoration(
            color: BankingTheme.surfaceCard,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: BankingTheme.borderSubtle),
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Namaste, $name', style: BankingTheme.headingLg),
                    const SizedBox(height: 2),
                    const Text('How can I help today?', style: BankingTheme.bodySm),
                  ],
                ),
              ),
              _Avatar(initials: initials),
            ],
          ),
        );
      },
    );
  }
}

class _Avatar extends StatelessWidget {
  const _Avatar({required this.initials});
  final String initials;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44, height: 44,
      decoration: const BoxDecoration(
        color: BankingTheme.surfaceSubtle,
        shape: BoxShape.circle,
      ),
      child: Center(
        child: Text(
          initials,
          style: const TextStyle(
            fontSize: 15, fontWeight: FontWeight.w600,
            color: BankingTheme.brandPrimary,
          ),
        ),
      ),
    );
  }
}

// ── Balance card ──────────────────────────────────────────────────────────────

class _BalanceCard extends StatelessWidget {
  const _BalanceCard({required this.store, required this.onTap});
  final HomeStore store;
  final void Function({String? message, String? contextLabel}) onTap;

  @override
  Widget build(BuildContext context) {
    return Observer(
      builder: (_) {
        final acct    = store.account;
        final label   = acct?.displayLabel ?? 'Savings ••1234';
        final balance = acct?.balance ?? 0.0;
        final hidden  = store.balanceHidden;

        return GestureDetector(
          onTap: () => onTap(message: 'Mera balance kya hai?', contextLabel: 'Balance'),
          child: Container(
            margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: BankingTheme.brandPrimary,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(label,
                        style: const TextStyle(
                          color: Colors.white70, fontSize: 13,
                          fontWeight: FontWeight.w500,
                        )),
                    _HideButton(hidden: hidden, onTap: store.toggleBalance),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  hidden
                      ? '₹ ••••••'
                      : '₹${balance.toStringAsFixed(0).replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+(?!\d))'), (m) => '${m[1]},')}',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 32, fontWeight: FontWeight.w700, height: 1.1,
                  ),
                ),
                const SizedBox(height: 4),
                const Text('Available balance',
                    style: TextStyle(color: Colors.white70, fontSize: 13)),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _HideButton extends StatelessWidget {
  const _HideButton({required this.hidden, required this.onTap});
  final bool hidden;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          hidden ? 'Show' : 'Hide',
          style: const TextStyle(
            color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

// ── Quick actions ─────────────────────────────────────────────────────────────

class _QuickActions extends StatelessWidget {
  const _QuickActions({required this.onTap});
  final void Function({String? message, String? contextLabel}) onTap;

  static const _actions = [
    ('Check balance', 'Mera balance kya hai?',         'Balance'),
    ('Send money',    'Send money',                    'Transfer money'),
    ('Open FD',       'Mujhe ek FD kholni hai',        'Open deposit'),
    ('Statement',     'Last week kitna kharch hua?',   'Spends'),
    ('Help & FAQ',    'FD ki minimum duration kya hai?', 'Ask anything'),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 20, 16, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Quick actions',
              style: TextStyle(
                fontSize: 15, fontWeight: FontWeight.w600,
                color: BankingTheme.contentPrimary,
              )),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final (label, msg, ctx) in _actions)
                ActionChip(
                  label: Text(label),
                  onPressed: () => onTap(message: msg, contextLabel: ctx),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

// ── Recent conversations ──────────────────────────────────────────────────────

class _RecentHeader extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.fromLTRB(16, 24, 16, 12),
      child: Text('Recent conversations',
          style: TextStyle(
            fontSize: 17, fontWeight: FontWeight.w600,
            color: BankingTheme.contentPrimary,
          )),
    );
  }
}

class _HistoryTile extends StatelessWidget {
  const _HistoryTile(this.record, {required this.onTap});
  final ConversationRecord record;
  final void Function({String? message, String? contextLabel}) onTap;

  String _timeAgo(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 1)  return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours   < 24) return '${diff.inHours}h ago';
    if (diff.inDays    < 7)  return '${diff.inDays}d ago';
    return '${dt.day}/${dt.month}';
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => onTap(
        message:      record.initialMessage,
        contextLabel: record.contextLabel,
      ),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 1),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: const BoxDecoration(
          color: BankingTheme.surfaceCard,
          border: Border(bottom: BorderSide(color: BankingTheme.borderSubtle)),
        ),
        child: Row(
          children: [
            Container(
              width: 40, height: 40,
              decoration: const BoxDecoration(
                color: BankingTheme.surfaceSubtle,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.chat_bubble_outline_rounded,
                  size: 20, color: BankingTheme.contentSecondary),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(record.title,
                      style: const TextStyle(
                        fontSize: 15, fontWeight: FontWeight.w500,
                        color: BankingTheme.contentPrimary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 3),
                  Row(
                    children: [
                      _TagChip(label: record.contextLabel ?? 'Chat'),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(record.subtitle,
                            style: const TextStyle(
                              fontSize: 12,
                              color: BankingTheme.contentSecondary,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(_timeAgo(record.timestamp),
                    style: const TextStyle(
                      fontSize: 12, color: BankingTheme.contentSecondary,
                    )),
                const SizedBox(height: 8),
                const Icon(Icons.chevron_right_rounded,
                    size: 18, color: BankingTheme.contentSecondary),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _TagChip extends StatelessWidget {
  const _TagChip({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: BankingTheme.surfaceSubtle,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(label,
          style: const TextStyle(
            fontSize: 11, fontWeight: FontWeight.w600,
            color: BankingTheme.brandPrimary,
          )),
    );
  }
}
