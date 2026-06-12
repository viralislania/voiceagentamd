import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:genui/genui.dart';
import 'package:genui_a2a/genui_a2a.dart';
import 'package:logging/logging.dart';

import '../catalog/catalog.dart';

final _log = Logger('AgentClient');

/// Low-level A2A SSE connection to the banking agent server.
///
/// Manages the connector, transport, surface controller, and conversation
/// lifecycle. Consumers subscribe to [surfaceUpdates], [errors], and
/// [conversationEvents] streams and call [sendMessage] to interact.
class AgentClient {
  AgentClient() {
    _log.info('Connecting to agent at ${_agentUrl()}');
    surfaceController = SurfaceController(
      catalogs: [BankingCatalog.asCatalog()],
    );
    _connector = A2uiAgentConnector(url: Uri.parse(_agentUrl()));
    _transport = A2uiTransportAdapter(
      onSend: (msg) => _connector.connectAndSend(msg),
    );

    _msgSub  = _connector.stream.listen(_transport.addMessage);
    _textSub = _connector.textStream.listen(_transport.addChunk);
    _errSub  = _connector.errorStream.listen((e) {
      _log.severe('Connector error', e);
      _errorSink.add(e);
    });

    surfaceController.surfaceUpdates.listen(_surfaceSink.add);

    _conversation = Conversation(
      transport: _transport,
      controller: surfaceController,
    );
  }

  late final SurfaceController surfaceController;
  late final A2uiAgentConnector _connector;
  late final A2uiTransportAdapter _transport;
  late final Conversation _conversation;

  late final StreamSubscription<A2uiMessage> _msgSub;
  late final StreamSubscription<String> _textSub;
  late final StreamSubscription<Object> _errSub;

  final _surfaceSink  = StreamController<SurfaceUpdate>.broadcast();
  final _errorSink    = StreamController<Object>.broadcast();

  Stream<SurfaceUpdate>     get surfaceUpdates      => _surfaceSink.stream;
  Stream<Object>            get errors              => _errorSink.stream;
  Stream<ConversationEvent> get conversationEvents  => _conversation.events;

  Future<void> sendMessage(String text) async {
    _log.fine('→ sendMessage: "$text"');
    await _conversation.sendRequest(ChatMessage.user(text));
    _log.fine('← sendMessage complete');
  }

  void dispose() {
    _log.info('Disposing AgentClient');
    _msgSub.cancel();
    _textSub.cancel();
    _errSub.cancel();
    _surfaceSink.close();
    _errorSink.close();
    _conversation.dispose();
    _transport.dispose();
    surfaceController.dispose();
    _connector.dispose();
  }

  static String _agentUrl() {
    if (!kIsWeb && Platform.isAndroid) return 'http://10.0.2.2:10002';
    return 'http://localhost:10002';
  }
}
