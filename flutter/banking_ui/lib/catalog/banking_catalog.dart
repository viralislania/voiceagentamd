import 'package:flutter/material.dart';
import 'package:genui/genui.dart';
import 'package:json_schema_builder/json_schema_builder.dart';

// catalogId must match Python's CATALOG_ID in src/a2ui.py
const String _kAgentCatalogId =
    'https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json';

// ── BankingTransactionRow ─────────────────────────────────────────────────────

final CatalogItem _bankingTransactionRow = CatalogItem(
  name: 'BankingTransactionRow',
  dataSchema: S.object(
    description: 'A transaction list row with debit/credit color coding.',
    properties: {
      'counterparty':   S.string(description: 'Payee or merchant name'),
      'meta':           S.string(description: 'Category · rail · date caption'),
      'amount_display': S.string(description: 'Pre-formatted amount, e.g. −₹2,000'),
      'is_debit':       S.boolean(description: 'true = red, false = green'),
    },
    required: ['counterparty', 'amount_display'],
  ),
  exampleData: [
    () => '''[
      {"id":"root","component":"BankingTransactionRow",
       "counterparty":"Swiggy","meta":"Food · UPI · 12 Jun",
       "amount_display":"−₹450","is_debit":true}
    ]''',
    () => '''[
      {"id":"root","component":"BankingTransactionRow",
       "counterparty":"Salary Credit","meta":"Income · NEFT · 1 Jun",
       "amount_display":"+₹85,000","is_debit":false}
    ]''',
  ],
  widgetBuilder: (ctx) {
    final d          = ctx.data as Map<String, dynamic>;
    final counterparty = d['counterparty']   as String? ?? '';
    final meta         = d['meta']           as String? ?? '';
    final amountStr    = d['amount_display'] as String? ?? '';
    final isDebit      = d['is_debit']       as bool?   ?? amountStr.startsWith('−');
    final failed       = amountStr == 'Failed';

    final cs = Theme.of(ctx.buildContext).colorScheme;
    final amountColor = failed
        ? cs.error
        : isDebit
            ? cs.error
            : const Color(0xFF0E9F6E);

    return InkWell(
      onTap: () => ctx.dispatchEvent(
        UserActionEvent(name: 'show_txn', sourceComponentId: ctx.id, context: {}),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(counterparty,
                      style: Theme.of(ctx.buildContext).textTheme.bodyMedium
                          ?.copyWith(fontWeight: FontWeight.w600)),
                  if (meta.isNotEmpty)
                    Text(meta,
                        style: Theme.of(ctx.buildContext).textTheme.labelSmall
                            ?.copyWith(color: cs.onSurfaceVariant)),
                ],
              ),
            ),
            Text(
              amountStr,
              style: Theme.of(ctx.buildContext).textTheme.bodyMedium
                  ?.copyWith(color: amountColor, fontWeight: FontWeight.w600),
            ),
          ],
        ),
      ),
    );
  },
);

// ── BankingAmountChip ─────────────────────────────────────────────────────────

final CatalogItem _bankingAmountChip = CatalogItem(
  name: 'BankingAmountChip',
  dataSchema: S.object(
    description: 'A compact INR amount chip with status color.',
    properties: {
      'amount':  S.string(description: 'Formatted INR string, e.g. ₹84,250'),
      'variant': S.string(
        description: 'Color variant: success | danger | neutral',
        enumValues: ['success', 'danger', 'neutral'],
      ),
    },
    required: ['amount'],
  ),
  exampleData: [
    () => '''[{"id":"root","component":"BankingAmountChip","amount":"₹84,250","variant":"success"}]''',
  ],
  widgetBuilder: (ctx) {
    final d       = ctx.data as Map<String, dynamic>;
    final amount  = d['amount']  as String? ?? '';
    final variant = d['variant'] as String? ?? 'neutral';
    final cs      = Theme.of(ctx.buildContext).colorScheme;

    final (bg, fg) = switch (variant) {
      'success' => (const Color(0xFFD1FAE5), const Color(0xFF0E9F6E)),
      'danger'  => (cs.errorContainer,       cs.onErrorContainer),
      _         => (cs.surfaceContainerHighest, cs.onSurface),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(amount,
          style: TextStyle(color: fg, fontWeight: FontWeight.w700, fontSize: 13)),
    );
  },
);

// ── BankingStatusBadge ────────────────────────────────────────────────────────

final CatalogItem _bankingStatusBadge = CatalogItem(
  name: 'BankingStatusBadge',
  dataSchema: S.object(
    description: 'A rounded status pill badge.',
    properties: {
      'label':  S.string(description: 'Badge text'),
      'status': S.string(
        description: 'open | closed | failed | success | pending',
        enumValues: ['open', 'closed', 'failed', 'success', 'pending'],
      ),
    },
    required: ['label'],
  ),
  exampleData: [
    () => '''[{"id":"root","component":"BankingStatusBadge","label":"Open · SLA 48h","status":"open"}]''',
  ],
  widgetBuilder: (ctx) {
    final d      = ctx.data as Map<String, dynamic>;
    final label  = d['label']  as String? ?? '';
    final status = d['status'] as String? ?? 'pending';
    final cs     = Theme.of(ctx.buildContext).colorScheme;

    final (bg, fg) = switch (status) {
      'open'    => (const Color(0xFFEBF5FF), const Color(0xFF1A56DB)),
      'closed'  => (cs.surfaceContainerHighest, cs.onSurfaceVariant),
      'failed'  => (cs.errorContainer,          cs.onErrorContainer),
      'success' => (const Color(0xFFD1FAE5),    const Color(0xFF0E9F6E)),
      _         => (cs.secondaryContainer,      cs.onSecondaryContainer),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(label, style: TextStyle(color: fg, fontSize: 12)),
    );
  },
);

// ── Catalog assembly ──────────────────────────────────────────────────────────

abstract final class BankingCatalog {
  BankingCatalog._();

  /// BasicCatalogItems + 3 banking-specific items, catalogId set to the
  /// agent's advertised value so createSurface messages are routed correctly.
  static Catalog asCatalog() => BasicCatalogItems.asCatalog().copyWith(
        catalogId: _kAgentCatalogId,
        newItems: [
          _bankingTransactionRow,
          _bankingAmountChip,
          _bankingStatusBadge,
        ],
      );
}
