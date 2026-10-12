# Changelog

## 0.3.0

- **Risikobereitschaft** im Dashboard: Vorsichtig, Ausgewogen oder Mutig. Die Stufe stellt die
  Grenzen pro Kauf, pro Coin, die Bargeld-Reserve und den Stop-Loss ein und wird Claude bei jeder
  Entscheidung mitgeteilt. Die Verlustgrenze gesamt bleibt immer.
- **Kein eigener Claude-Token mehr nötig:** Der Trader fragt Claude über das Inkbox Claude
  Gateway (ab 0.12.0) und nutzt dessen Anmeldung. Behebt „Not logged in · /login“.
- Klarer Hinweis im Dashboard, wenn Claude nicht erreichbar oder nicht angemeldet ist.

## 0.2.0

- Claude entscheidet **alle 3 Stunden** (einstellbar) statt einmal täglich, mit Stunden-Kursen
  (3 h, 24 h, RSI) zusätzlich zu den Tageskursen.
- **Coins automatisch:** die meistgehandelten Coins der Börse inklusive kleiner, mit
  Mindest-Umsatz; Stablecoins ausgenommen. Kleine Coins höchstens 10 % des Gesamtwerts.
- Startbudget 500 €, Sicherheitsprüfung alle 15 Minuten, bis zu 12 Orders am Tag.
- iMessage nur noch bei Trades sofort, dazu ein Tagesbericht.

## 0.1.0

- Erste Version: tägliche Entscheidungen durch Claude Code (mit Websuche) über mehrere
  Kryptowährungen, Papertrading mit echten Kursen und simulierten Gebühren, umschaltbar auf
  echtes Trading über ccxt (Kraken, Coinbase, Binance, Bitvavo).
- Feste Regeln: Budget, Anteil pro Kauf und Coin, Bargeld-Reserve, stündlicher Stop-Loss,
  Verlustgrenze mit automatischem Verkauf und Stopp, Tageslimit für Orders.
- Dashboard mit Vergleich zu „nur Bitcoin halten“, Entscheidungen mit Begründung, Not-Aus,
  CSV-Export; täglicher Bericht und Warnungen per iMessage.
