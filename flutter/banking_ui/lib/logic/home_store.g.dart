// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'home_store.dart';

// **************************************************************************
// StoreGenerator
// **************************************************************************

// ignore_for_file: non_constant_identifier_names, unnecessary_brace_in_string_interps, unnecessary_lambdas, prefer_expression_function_bodies, lines_longer_than_80_chars, avoid_as, avoid_annotating_with_dynamic, no_leading_underscores_for_local_identifiers

mixin _$HomeStore on _HomeStore, Store {
  late final _$profileAtom = Atom(name: '_HomeStore.profile', context: context);

  @override
  CustomerProfile? get profile {
    _$profileAtom.reportRead();
    return super.profile;
  }

  @override
  set profile(CustomerProfile? value) {
    _$profileAtom.reportWrite(value, super.profile, () {
      super.profile = value;
    });
  }

  late final _$accountAtom = Atom(name: '_HomeStore.account', context: context);

  @override
  AccountSummary? get account {
    _$accountAtom.reportRead();
    return super.account;
  }

  @override
  set account(AccountSummary? value) {
    _$accountAtom.reportWrite(value, super.account, () {
      super.account = value;
    });
  }

  late final _$isLoadingAtom = Atom(
    name: '_HomeStore.isLoading',
    context: context,
  );

  @override
  bool get isLoading {
    _$isLoadingAtom.reportRead();
    return super.isLoading;
  }

  @override
  set isLoading(bool value) {
    _$isLoadingAtom.reportWrite(value, super.isLoading, () {
      super.isLoading = value;
    });
  }

  late final _$balanceHiddenAtom = Atom(
    name: '_HomeStore.balanceHidden',
    context: context,
  );

  @override
  bool get balanceHidden {
    _$balanceHiddenAtom.reportRead();
    return super.balanceHidden;
  }

  @override
  set balanceHidden(bool value) {
    _$balanceHiddenAtom.reportWrite(value, super.balanceHidden, () {
      super.balanceHidden = value;
    });
  }

  late final _$errorMessageAtom = Atom(
    name: '_HomeStore.errorMessage',
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

  late final _$loadAsyncAction = AsyncAction(
    '_HomeStore.load',
    context: context,
  );

  @override
  Future<void> load() {
    return _$loadAsyncAction.run(() => super.load());
  }

  late final _$_HomeStoreActionController = ActionController(
    name: '_HomeStore',
    context: context,
  );

  @override
  void toggleBalance() {
    final _$actionInfo = _$_HomeStoreActionController.startAction(
      name: '_HomeStore.toggleBalance',
    );
    try {
      return super.toggleBalance();
    } finally {
      _$_HomeStoreActionController.endAction(_$actionInfo);
    }
  }

  @override
  void clearError() {
    final _$actionInfo = _$_HomeStoreActionController.startAction(
      name: '_HomeStore.clearError',
    );
    try {
      return super.clearError();
    } finally {
      _$_HomeStoreActionController.endAction(_$actionInfo);
    }
  }

  @override
  String toString() {
    return '''
profile: ${profile},
account: ${account},
isLoading: ${isLoading},
balanceHidden: ${balanceHidden},
errorMessage: ${errorMessage}
    ''';
  }
}
