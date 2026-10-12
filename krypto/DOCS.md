# Krypto-Trader

Claude handelt für dich Kryptowährungen: **alle 3 Stunden** (einstellbar) schaut er sich Kurse,
Trends und Nachrichten an und entscheidet, was gekauft, verkauft oder gehalten wird – jeweils mit
Begründung. Standardmäßig wählt er aus den **meistgehandelten Coins der Börse**, auch kleinen. Feste Regeln im Add-on begrenzen das Risiko, egal was Claude entscheidet.

> **Ehrlich gesagt:** Niemand – auch keine KI – kann Gewinne garantieren. Die meisten
> Trading-Bots schneiden auf Dauer schlechter ab als einfaches Halten. Deshalb startet der
> Trader im **Papertrading** (echte Kurse, simuliertes Geld) und vergleicht sich ständig mit
> „nur Bitcoin halten“ und „alle Coins gleich halten“. Erst wenn das über Wochen überzeugt,
> lohnt sich echtes Geld – und dann nur Geld, dessen Verlust du verkraften kannst.

## So läuft es

- **Alle 3 Stunden** entscheidet Claude (über die Anmeldung deines Inkbox Claude Gateways). Wird gehandelt, kommt
  sofort eine iMessage mit Begründung; abends (einstellbar) ein Tagesbericht mit Vergleich.
- **Coins:** `auto` = die 40 meistgehandelten Coins mit mindestens 250.000 € Tagesumsatz
  (Stablecoins wie USDT ausgenommen). Oder eine feste Liste, z. B. `BTC,ETH,SOL`.
- **Alle 15 Minuten** prüft das Add-on ohne Claude:
  - **Stop-Loss:** Ein Coin, der z. B. 12 % unter seinem Einkaufspreis liegt, wird verkauft.
  - **Verlustgrenze gesamt:** Liegt das Handelskapital z. B. 20 % unter dem Start, wird alles verkauft und
    gestoppt. Weiter geht es nur, wenn du es freigibst.
- **Weitere feste Regeln:** nie mehr als das Budget (Vorgabe 500 €), höchstens 25 % pro Kauf,
  40 % pro großem Coin (BTC, ETH, SOL, XRP, ADA, DOGE, LINK …) und **10 % pro kleinem Coin**,
  mindestens 10 % Bargeld, höchstens 12 Orders am Tag.
- **Nachrichten:** Claude stützt seine Entscheidungen auf die Nachrichten deiner Quellen
  (Option **Nachrichtenquellen**, vorgegeben CoinDesk, Cointelegraph, Decrypt und BTC-ECHO; jede
  Webseite mit RSS-Feed geht). Eine allgemeine Websuche macht er dann nicht, er darf nur Artikel
  dieser Quellen öffnen. Bei jedem Trade steht, auf welcher Nachricht er beruht. Nachrichten sind
  für Claude nur Information, keine Anweisung, und die festen Regeln gelten trotzdem.
- **Gewinn-Coins (getaggt):** Claude kauft und verkauft nach eigenem Ermessen. Verkauft er eine
  Position mit Gewinn, wird nur der Einkaufspreis plus volle 10-%-Stufen verkauft:

  | Gewinn beim Verkauf | verkauft (wieder eingesetzt) | bleibt als getaggter Coin |
  |---|---|---|
  | +4 % | Einkaufspreis | 4 % |
  | +12 % | Einkaufspreis + 10 % | 2 % |
  | +27 % | Einkaufspreis + 20 % | 7 % |
  | +39 % | Einkaufspreis + 30 % | 9 % |

  Beispiel: für 50 € gekauft, für 70 € verkauft (+40 %) → alles verkauft. Für 500 € gekauft, bei
  520 € verkauft → 500 € verkauft, 20 € bleiben als Coin. Getaggte Coins werden **nie
  verkauft** – weder von Claude noch von Stop-Loss, Verlustgrenze oder Not-Aus. Sie zählen zum
  Gesamtwert, und beim endgültigen Stopp rechnest du sie zum Gewinn. Die Stufe ist unter
  **Gewinnstufe** einstellbar (0 = aus). Verluste werden ganz normal verkauft.
- **Risikobereitschaft** im Dashboard umschaltbar:

  | Stufe | pro Kauf | großer Coin | kleiner Coin | Bargeld mind. | Stop-Loss |
  |---|---|---|---|---|---|
  | 🛡️ Vorsichtig | 15 % | 30 % | 5 % | 30 % | −8 % |
  | ⚖️ Ausgewogen | deine Optionen (Vorgabe 25 / 40 / 10 / 10 / −12 %) |||||
  | 🚀 Mutig | 35 % | 50 % | 20 % | 5 % | −18 % |

  Claude bekommt die Stufe mitgeteilt und richtet seine Entscheidungen danach. Die
  Verlustgrenze gesamt gilt immer. Umstellen kannst nur du – Claude kann die Stufe nicht ändern.
- **Dashboard** in der Seitenleiste (**Krypto**): Wert, Verlauf mit Vergleichslinien, Bestand,
  alle Entscheidungen mit Begründung, Stopp/Not-Aus, CSV-Export.
- **Per iMessage** (mit dem Gateway ab 0.11.0): „Wie läuft der Krypto-Trader?“,
  „Warum hat er gestern verkauft?“, „Trading stopp“, „Not-Aus, alles verkaufen“.

## Einrichtung (Papertrading)

1. **Claude:** nichts eintragen. Der Trader fragt Claude über dein **Inkbox Claude Gateway
   (ab 0.12.0)** und nutzt dessen Anmeldung. Das Gateway muss laufen; nach einem Gateway-Update
   erst das Gateway, dann den Trader neu starten. Nur wenn du das Gateway nicht nutzt: einen
   eigenen Token aus `claude setup-token` bei **Claude-Token** eintragen.
2. **Inkbox API-Key** und **Handynummer** für die Berichte.
3. Budget, Coins, Uhrzeit und Grenzen nach Wunsch, Börse für die Kurse (Vorgabe Kraken).
4. Starten. Die erste Entscheidung kommt gleich nach dem Start, dann alle 3 Stunden; im
   Dashboard geht auch „Jetzt entscheiden lassen“.

Jede Entscheidung verbraucht etwas von deinem Claude-Kontingent – alle 3 Stunden sind 8 am Tag.
Kleine Coins schwanken extrem (−30 % an einem Tag kommt vor); Stop-Loss und die 10-%-Grenze
pro kleinem Coin begrenzen das, verhindern Verluste aber nicht.

## „Not logged in · /login“

Diese Meldung heißt: Claude ist im Trader nicht angemeldet. Lösung: Gateway auf 0.12.0 oder
neuer aktualisieren und neu starten, danach den Trader neu starten und das Feld Claude-Token
leer lassen. Im Dashboard verschwindet dann der rote Hinweis.

## Umstellen auf echtes Geld (erst nach einer Testphase!)

1. Bei der Börse ein **eigenes Unterkonto bzw. Portfolio** anlegen und nur das Geld
   hineinlegen, mit dem gehandelt werden darf (z. B. Coinbase Advanced → Portfolios,
   Kraken → Subaccount).
2. Dafür einen **API-Key nur mit Handelsrecht** erstellen – **ohne Auszahlungsrecht**. So kann
   niemand Geld abziehen, selbst wenn der Schlüssel in falsche Hände gerät.
3. Im Add-on: `mode` = `live`, Börse, API-Key/Secret eintragen und bei
   **Echtgeld-Bestätigung** genau `ICH TRAGE DAS RISIKO` schreiben. Neu starten.
4. Es beginnt ein neues Konto mit dem Budget. Gehandelt wird höchstens das Budget und nie mehr,
   als wirklich auf dem Konto liegt. Das Papier-Konto wird archiviert.

Claude selbst kann nie auf echtes Geld umschalten, Grenzen ändern oder nach einem Stopp
weitermachen – das geht nur über dich.

## Steuern

In Deutschland sind Gewinne aus Coins, die weniger als ein Jahr gehalten wurden, als privates
Veräußerungsgeschäft steuerpflichtig (Freigrenze 1.000 € pro Jahr). Die Datei
**Trades als CSV** im Dashboard enthält alle Käufe und Verkäufe mit Kurs und Gebühr.
