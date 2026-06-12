import 'package:logging/logging.dart';
import 'package:mobx/mobx.dart';

import '../api/banking_api.dart';

part 'home_store.g.dart';

final _log = Logger('HomeStore');

// Run `dart run build_runner build` after modifying this file.
class HomeStore = _HomeStore with _$HomeStore;

abstract class _HomeStore with Store {
  _HomeStore({
    BankingApiService? api,
    this.customerId = 'CUST001',
    this.accountId  = 'ACC001',
  }) : _api = api ?? BankingApiService();

  final BankingApiService _api;
  final String customerId;
  final String accountId;

  @observable
  CustomerProfile? profile;

  @observable
  AccountSummary? account;

  @observable
  bool isLoading = false;

  @observable
  bool balanceHidden = false;

  @observable
  String? errorMessage;

  @action
  void toggleBalance() => balanceHidden = !balanceHidden;

  @action
  Future<void> load() async {
    _log.info('HomeStore.load customer=$customerId account=$accountId');
    isLoading    = true;
    errorMessage = null;
    try {
      final results = await Future.wait([
        _api.getCustomer(customerId),
        _api.getBalance(accountId),
      ]);
      profile = results[0] as CustomerProfile;
      account = results[1] as AccountSummary;
      _log.fine('HomeStore.load done: ${profile!.name} ₹${account!.balance}');
    } catch (e, st) {
      _log.severe('HomeStore.load failed', e, st);
      errorMessage = e.toString();
    } finally {
      isLoading = false;
    }
  }

  @action
  void clearError() => errorMessage = null;
}
