# Krypto-Trader

Claude handelt für dich Kryptowährungen: **einmal am Tag** schaut er sich Kurse, Trends und
Nachrichten an und entscheidet, was gekauft, verkauft oder gehalten wird – jeweils mit
Begründung. Feste Regeln im Add-on begrenzen das Risiko, egal was Claude entscheidet.

> **Ehrlich gesagt:** Niemand – auch keine KI – kann Gewinne garantieren. Die meisten
> Trading-Bots schneiden auf Dauer schlechter ab als einfaches Halten. Deshalb startet der
> Trader im **Papertrading** (echte Kurse, simuliertes Geld) und vergleicht sich ständig mit
> „nur Bitcoin halten“ und „alle Coins gleich halten“. Erst wenn das über Wochen überzeugt,
> lohnt sich echtes Geld – und dann nur Geld, dessen Verlust du verkraften kannst.

## So läuft es

- **Täglich ab der eingestellten Uhrzeit** entscheidet Claude (Claude Code mit deinem Token).
  Du bekommst eine iMessage mit Wert, Vergleich, Begründung und den Trades.
- **Stündlich** prüft das Add-on ohne Claude:
  - **Stop-Loss:** Ein Coin, der z. B. 12 % unter seinem Einkaufspreis liegt, wird verkauft.
  - **Verlustgrenze gesamt:** Liegt alles z. B. 20 % unter dem Start, wird alles verkauft und
    gestoppt. Weiter geht es nur, wenn du es freigibst.
- **Weitere feste Regeln:** nie mehr als das Budget, höchstens 25 % pro Kauf und 40 % pro Coin,
  mindestens 10 % Bargeld, nur die erlaubten Coins, höchstens 6 Orders am Tag.
- **Dashboard** in der Seitenleiste (**Krypto**): Wert, Verlauf mit Vergleichslinien, Bestand,
  alle Entscheidungen mit Begründung, Stopp/Not-Aus, CSV-Export.
- **Per iMessage** (mit dem Gateway ab 0.11.0): „Wie läuft der Krypto-Trader?“,
  „Warum hat er gestern verkauft?“, „Trading stopp“, „Not-Aus, alles verkaufen“.

## Einrichtung (Papertrading)

1. **Claude-Token** eintragen (derselbe wie im Gateway, aus `claude setup-token`).
2. **Inkbox API-Key** und **Handynummer** für die Berichte.
3. Budget, Coins, Uhrzeit und Grenzen nach Wunsch, Börse für die Kurse (Vorgabe Kraken).
4. Starten. Die erste Entscheidung kommt ab der eingestellten Uhrzeit; im Dashboard geht
   auch „Jetzt entscheiden lassen“.

Jede Entscheidung verbraucht etwas von deinem Claude-Kontingent (einmal am Tag).

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
