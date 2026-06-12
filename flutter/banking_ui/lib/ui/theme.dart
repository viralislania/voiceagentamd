import 'package:flutter/material.dart';

/// Design tokens — Banking Voice Agent Design System.
///
/// Source: screens/design-system.png
/// Semantic names mirror Figma layer names so diffs stay readable.
abstract final class BankingTheme {
  BankingTheme._();

  // ── Color tokens ─────────────────────────────────────────────────────────
  static const Color brandPrimary      = Color(0xFF0B5FFF); // brand/primary
  static const Color surfaceBackground = Color(0xFFF6F8FB); // surface/background
  static const Color surfaceCard       = Color(0xFFFFFFFF); // surface/card
  static const Color surfaceSubtle     = Color(0xFFEEF2F8); // surface/subtle
  static const Color contentPrimary    = Color(0xFF0E1726); // content/primary
  static const Color contentSecondary  = Color(0xFF5B6675); // content/secondary
  static const Color statusSuccess     = Color(0xFF0E9F6E); // status/success
  static const Color statusDanger      = Color(0xFFE02424); // status/danger
  static const Color statusWarning     = Color(0xFFC27803); // status/warning
  static const Color borderSubtle      = Color(0xFFE2E8F0); // border/subtle

  // Derived aliases used throughout UI code
  static const Color userBubble  = brandPrimary;
  static const Color agentBubble = surfaceSubtle;

  // ── Type scale ────────────────────────────────────────────────────────────
  // display/amount  32/40 · 700
  static const TextStyle displayAmount = TextStyle(
    fontSize: 32, height: 40 / 32, fontWeight: FontWeight.w700,
    color: contentPrimary,
  );
  // heading/lg  20/28 · 600
  static const TextStyle headingLg = TextStyle(
    fontSize: 20, height: 28 / 20, fontWeight: FontWeight.w600,
    color: contentPrimary,
  );
  // body/md  15/22 · 400
  static const TextStyle bodyMd = TextStyle(
    fontSize: 15, height: 22 / 15, fontWeight: FontWeight.w400,
    color: contentPrimary,
  );
  // body/sm  13/18 · 400  — captions & metadata
  static const TextStyle bodySm = TextStyle(
    fontSize: 13, height: 18 / 13, fontWeight: FontWeight.w400,
    color: contentSecondary,
  );
  // label/md  14/20 · 600  — buttons / chips
  static const TextStyle labelMd = TextStyle(
    fontSize: 14, height: 20 / 14, fontWeight: FontWeight.w600,
    color: brandPrimary,
  );

  // ── Light theme ───────────────────────────────────────────────────────────
  static ThemeData get light {
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: brandPrimary,
        surface: surfaceCard,
      ),
      scaffoldBackgroundColor: surfaceBackground,

      appBarTheme: const AppBarTheme(
        backgroundColor: surfaceCard,
        foregroundColor: contentPrimary,
        elevation: 0,
        scrolledUnderElevation: 1,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: TextStyle(
          fontSize: 18, fontWeight: FontWeight.w600,
          color: contentPrimary,
        ),
      ),

      cardTheme: CardThemeData(
        elevation: 0,
        color: surfaceCard,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: borderSubtle),
        ),
        margin: EdgeInsets.zero,
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceCard,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(28),
          borderSide: const BorderSide(color: borderSubtle),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(28),
          borderSide: const BorderSide(color: borderSubtle),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(28),
          borderSide: const BorderSide(color: brandPrimary, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        hintStyle: const TextStyle(color: contentSecondary, fontSize: 14),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: brandPrimary,
          foregroundColor: surfaceCard,
          minimumSize: const Size(0, 48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
          elevation: 0,
        ),
      ),

      chipTheme: ChipThemeData(
        backgroundColor: surfaceSubtle,
        labelStyle: const TextStyle(
          color: brandPrimary, fontSize: 14, fontWeight: FontWeight.w600,
        ),
        side: BorderSide.none,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 0),
      ),

      dividerTheme: const DividerThemeData(
        color: borderSubtle,
        thickness: 1,
        space: 0,
      ),
    );
  }

  // ── Dark theme (minimal — inherits from seed) ─────────────────────────────
  static ThemeData get dark {
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: brandPrimary,
        brightness: Brightness.dark,
      ),
    );
  }
}
