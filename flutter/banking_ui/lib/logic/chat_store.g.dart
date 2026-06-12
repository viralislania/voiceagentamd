// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'chat_store.dart';

// **************************************************************************
// StoreGenerator
// **************************************************************************

// ignore_for_file: non_constant_identifier_names, unnecessary_brace_in_string_interps, unnecessary_lambdas, prefer_expression_function_bodies, lines_longer_than_80_chars, avoid_as, avoid_annotating_with_dynamic, no_leading_underscores_for_local_identifiers

mixin _$ChatStore on _ChatStore, Store {
  late final _$isProcessingAtom = Atom(
    name: '_ChatStore.isProcessing',
    context: context,
  );

  @override
  bool get isProcessing {
    _$isProcessingAtom.reportRead();
    return super.isProcessing;
  }

  @override
  set isProcessing(bool value) {
    _$isProcessingAtom.reportWrite(value, super.isProcessing, () {
      super.isProcessing = value;
    });
  }

  late final _$errorMessageAtom = Atom(
    name: '_ChatStore.errorMessage',
    context: context,
  );

  @override
  String? get errorMessage {
    _$errorMessageAtom.reportRead();
    return super.errorMessage;
  }

  @override
  set errorMessage(String? value) {
    _$errorMessageAtom.reportWrite(value, super.errorMessage, () {
      super.errorMessage = value;
    });
  }

  late final _$sendMessageAsyncAction = AsyncAction(
    '_ChatStore.sendMessage',
    context: context,
  );

  @override
  Future<void> sendMessage(String text) {
    return _$sendMessageAsyncAction.run(() => super.sendMessage(text));
  }

  late final _$_ChatStoreActionController = ActionController(
    name: '_ChatStore',
    context: context,
  );

  @override
  void clearError() {
    final _$actionInfo = _$_ChatStoreActionController.startAction(
      name: '_ChatStore.clearError',
    );
    try {
      return super.clearError();
    } finally {
      _$_ChatStoreActionController.endAction(_$actionInfo);
    }
  }

  @override
  String toString() {
    return '''
isProcessing: ${isProcessing},
errorMessage: ${errorMessage}
    ''';
  }
}
