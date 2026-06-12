import 'package:flutter/material.dart';
import 'package:logging/logging.dart';

import 'ui/home_screen.dart';
import 'ui/theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  Logger.root.level = Level.ALL;
  Logger.root.onRecord.listen((r) {
    debugPrint('[${r.loggerName}] ${r.level.name}: ${r.message}');
    if (r.error      != null) debugPrint('  error: ${r.error}');
    if (r.stackTrace != null) debugPrint('  ${r.stackTrace}');
  });
  runApp(const BankingApp());
}

class BankingApp extends StatelessWidget {
  const BankingApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Banking Assistant',
      debugShowCheckedModeBanner: false,
      theme: BankingTheme.light,
      darkTheme: BankingTheme.dark,
      home: const HomeScreen(),
    );
  }
}
