import 'dart:convert';

enum MessageRole { user, agent }

/// A persisted summary of a completed chat session, stored in device cache.
class ConversationRecord {
  ConversationRecord({
    required this.title,
    required this.subtitle,
    required this.timestamp,
    this.isVoice = false,
    this.initialMessage,
    this.contextLabel,
  });

  factory ConversationRecord.fromJson(Map<String, dynamic> j) =>
      ConversationRecord(
        title:          j['title']           as String,
        subtitle:       j['subtitle']        as String? ?? '',
        timestamp:      DateTime.parse(j['timestamp'] as String),
        isVoice:        j['is_voice']        as bool?   ?? false,
        initialMessage: j['initial_message'] as String?,
        contextLabel:   j['context_label']   as String?,
      );

  Map<String, dynamic> toJson() => {
        'title':     title,
        'subtitle':  subtitle,
        'timestamp': timestamp.toIso8601String(),
        'is_voice':  isVoice,
        if (initialMessage != null) 'initial_message': initialMessage,
        if (contextLabel   != null) 'context_label':   contextLabel,
      };

  final String   title;
  final String   subtitle;
  final DateTime timestamp;
  final bool     isVoice;
  final String?  initialMessage;
  final String?  contextLabel;
}

/// A single message in the banking chat conversation.
///
/// [text] is mutable so streaming chunks can be appended in-place.
class BankingMessage {
  BankingMessage.user(String text)
      : role     = MessageRole.user,
        text     = text,
        surfaceId = null,
        timestamp = DateTime.now();

  BankingMessage.agent({String? text, this.surfaceId})
      : role      = MessageRole.agent,
        text      = text,
        timestamp = DateTime.now();

  final MessageRole role;
  String? text;        // mutable: streaming chunks appended here
  final String? surfaceId;
  final DateTime timestamp;

  bool get isUser     => role == MessageRole.user;
  bool get hasSurface => surfaceId != null;
}
