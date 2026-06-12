import 'dart:async';

import 'package:genui/genui.dart';
import 'package:logging/logging.dart';
import 'package:mobx/mobx.dart';

import '../api/agent_client.dart';
import 'models.dart';

part 'chat_store.g.dart';

final _log = Logger('ChatStore');

// Run `dart run build_runner build` after modifying this file.
class ChatStore = _ChatStore with _$ChatStore;

abstract class _ChatStore with Store {
  _ChatStore({this.onConversationStarted}) {
    _client = AgentClient();
    _wireSubscriptions();
  }

  /// Called once with the first user message text so callers can persist it.
  final void Function(String message)? onConversationStarted;

  late final AgentClient _client;

  /// Exposes the surface controller for genui Surface widgets.
  AgentClient get client => _client;

  final messages = ObservableList<BankingMessage>();

  @observable
  bool isProcessing = false;

  @observable
  String? errorMessage;

  BankingMessage? _pendingAgentMessage;

  void _wireSubscriptions() {
    _client.surfaceUpdates.listen((update) {
      switch (update) {
        case SurfaceAdded(:final surfaceId):
          if (!messages.any((m) => m.surfaceId == surfaceId)) {
            runInAction(
              () => messages.add(BankingMessage.agent(surfaceId: surfaceId)),
            );
          }
        default:
          break;
      }
    });

    _client.errors.listen((error) {
      _log.severe('Agent error received in store', error);
      runInAction(() {
        messages.add(BankingMessage.agent(text: 'Connection error: $error'));
        isProcessing  = false;
        errorMessage  = error.toString();
      });
    });
  }

  @action
  Future<void> sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || isProcessing) return;

    _log.info('ChatStore.sendMessage: "$trimmed"');
    final isFirst = messages.isEmpty;
    messages.add(BankingMessage.user(trimmed));
    if (isFirst) onConversationStarted?.call(trimmed);
    _pendingAgentMessage = null;
    isProcessing  = true;
    errorMessage  = null;

    final sub = _client.conversationEvents.listen(_handleEvent);
    try {
      await _client.sendMessage(trimmed);
      _log.fine('ChatStore.sendMessage: completed');
    } catch (e, st) {
      _log.severe('ChatStore.sendMessage: failed', e, st);
      runInAction(() {
        messages.add(BankingMessage.agent(text: 'Error: $e'));
        errorMessage = e.toString();
      });
    } finally {
      await sub.cancel();
      runInAction(() => isProcessing = false);
    }
  }

  void _handleEvent(ConversationEvent event) {
    if (event is ConversationContentReceived) {
      runInAction(() {
        if (_pendingAgentMessage == null) {
          // First chunk — add a new empty agent bubble
          _pendingAgentMessage = BankingMessage.agent(text: event.text);
          messages.add(_pendingAgentMessage!);
        } else {
          // Subsequent chunks — replace at index so ObservableList tracks the change
          final idx = messages.indexOf(_pendingAgentMessage!);
          if (idx >= 0) {
            final updated = BankingMessage.agent(
              text: (_pendingAgentMessage!.text ?? '') + event.text,
            );
            messages[idx]        = updated;
            _pendingAgentMessage = updated;
          }
        }
      });
    }
  }

  @action
  void clearError() => errorMessage = null;

  void dispose() {
    _log.info('ChatStore.dispose');
    _pendingAgentMessage = null;
    _client.dispose();
  }
}
