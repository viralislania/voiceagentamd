import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';

class HistoryService {
  static const _key = 'conversation_history_v1';
  static const _max = 5;  // Keep last 5 conversations only

  Future<List<ConversationRecord>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw   = prefs.getString(_key);
    if (raw == null) return [];
    try {
      final list = jsonDecode(raw) as List;
      return list
          .map((e) => ConversationRecord.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> add(ConversationRecord record) async {
    final prefs    = await SharedPreferences.getInstance();
    final existing = await load();
    final updated  = [record, ...existing].take(_max).toList();
    await prefs.setString(
      _key,
      jsonEncode(updated.map((r) => r.toJson()).toList()),
    );
  }
}
