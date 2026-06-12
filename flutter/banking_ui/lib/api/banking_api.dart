import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:logging/logging.dart';

final _log = Logger('BankingApi');

/// Direct REST client for the FastAPI mock bank backend (port 8000).
///
/// Separate from [AgentClient] which handles A2A SSE to the agent (port 10002).
class BankingApiService {
  static String _base() {
    if (!kIsWeb && Platform.isAndroid) return 'http://10.0.2.2:8000/open-banking/v1';
    return 'http://localhost:8000/open-banking/v1';
  }

  Future<CustomerProfile> getCustomer(String customerId) async {
    final uri  = Uri.parse('${_base()}/customers/$customerId');
    _log.fine('GET $uri');
    final resp = await http.get(uri);
    if (resp.statusCode != 200) {
      throw Exception('getCustomer failed: ${resp.statusCode}');
    }
    final data = (jsonDecode(resp.body) as Map)['Data'] as Map<String, dynamic>;
    return CustomerProfile.fromJson(data);
  }

  Future<AccountSummary> getBalance(String accountId) async {
    final uri  = Uri.parse('${_base()}/accounts/$accountId/balances');
    _log.fine('GET $uri');
    final resp = await http.get(uri);
    if (resp.statusCode != 200) {
      throw Exception('getBalance failed: ${resp.statusCode}');
    }
    final data = (jsonDecode(resp.body) as Map)['Data'] as Map<String, dynamic>;
    return AccountSummary.fromJson(data);
  }
}

// ── Data models ───────────────────────────────────────────────────────────────

class CustomerProfile {
  const CustomerProfile({
    required this.customerId,
    required this.name,
    required this.avatarInitials,
  });

  factory CustomerProfile.fromJson(Map<String, dynamic> j) => CustomerProfile(
        customerId:     j['customer_id'] as String,
        name:           j['name'] as String,
        avatarInitials: j['avatar_initials'] as String? ?? '??',
      );

  final String customerId;
  final String name;
  final String avatarInitials;

  String get firstName => name.split(' ').first;
}

class AccountSummary {
  const AccountSummary({
    required this.accountId,
    required this.nickname,
    required this.maskedNumber,
    required this.balance,
    required this.currency,
  });

  factory AccountSummary.fromJson(Map<String, dynamic> j) => AccountSummary(
        accountId:    j['account_id'] as String,
        nickname:     j['nickname'] as String? ?? 'Savings',
        maskedNumber: j['masked_number'] as String? ?? '••••',
        balance:      (j['balance'] as num).toDouble(),
        currency:     j['currency'] as String? ?? 'INR',
      );

  final String accountId;
  final String nickname;
  final String maskedNumber;
  final double balance;
  final String currency;

  String get displayLabel => '$nickname $maskedNumber';
}
