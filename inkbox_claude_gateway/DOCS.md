# Inkbox Claude Gateway

Dieses Add-on lässt den Inkbox-Gateway dauerhaft auf deinem Home Assistant
laufen. Kommt eine E-Mail oder iMessage für deine Inkbox-Identität an, startet
der Gateway eine Claude-Code-Sitzung, die im selben Chat antwortet.

Basis: [inkbox-ai/claude-code-plugin](https://github.com/inkbox-ai/claude-code-plugin),
fest auf einen Commit gepinnt (siehe `Dockerfile`).

Voraussetzung: Home Assistant **OS** oder **Supervised** auf `amd64` oder `aarch64`.

## Installation

1. *Einstellungen → Add-ons → Add-on Store* → oben rechts **⋮ → Repositories**.
2. `https://github.com/fvh02/fabiaiagent` hinzufügen und schließen.
3. **Inkbox Claude Gateway** im Store öffnen → **Installieren**. Der erste Build dauert ein paar Minuten.

## Einrichtung

Alle Zugangsdaten trägst du im Tab **Konfiguration** des Add-ons ein. Sie werden
nur auf deinem Home Assistant gespeichert, Schlüssel werden verdeckt angezeigt.

| Feld | Was eintragen |
|---|---|
| Inkbox-API-Key | API-Key aus deinem Inkbox-Konto. |
| Inkbox-Identität | Handle deiner Identität, ohne `@`. |
| Claude-OAuth-Token | Für ein Claude-Abo: auf einem Rechner mit Claude Code `claude setup-token` ausführen und das Token einfügen. |
| Anthropic-API-Key | Alternative zum Token (Abrechnung pro Token). Eins von beiden reicht. |
| Antwortsprache | Sprache, in der Claude antwortet (Standard: Deutsch). Schreibst du in einer anderen Sprache oder schickst eine Datei in einer anderen Sprache, antwortet Claude in dieser. „Automatisch“ = keine Vorgabe. |
| Arbeitsordner | Standard `/share/claude-workspace`. |
| Voice AI | Nur wenn die Identität eine Telefonnummer hat. |
| Claude-Modell | Optional, leer = Standard. |

**Speichern**, dann im Tab **Info** „Beim Booten starten“ und „Watchdog“
aktivieren und **Starten**.

## Prüfen

Im Tab **Protokoll** sollte stehen:

- ein JSON-Block mit `"status": "configured"`
- die Ausgabe von `inkbox-claude doctor` mit ✓ bei `INKBOX_API_KEY`,
  `INKBOX_IDENTITY`, `INKBOX_SIGNING_KEY` und `Claude readiness`
- danach die Logs des laufenden Gateways

Dann eine iMessage oder E-Mail an deine Identität schicken. Die Antwort kommt im
selben Chat. `/health` im Chat liefert einen Statusbericht.

## Wissenswertes

- **Signing-Key:** Beim ersten Start erzeugt das Add-on einen neuen
  Webhook-Signing-Key für die Identität. Ein anderer Gateway für dieselbe
  Identität empfängt danach nichts mehr. Spätere Neustarts verwenden den
  gespeicherten Key weiter.
- **Daten** liegen im privaten Add-on-Speicher (`/data`) und bleiben bei
  Neustarts und Updates erhalten. Sie sind Teil deiner Home-Assistant-Backups.
- **Freigaben:** Will Claude Befehle ausführen oder Dateien ändern, schickt dir
  der Gateway eine kurze Zusammenfassung. Antworte mit `1`/`yes`,
  `2`/`always` oder `3`/`no`.
- **Antwortsprache ändern:** Im Tab Konfiguration auswählen, speichern und das
  Add-on neu starten. Mit `/new` im Chat startest du danach eine frische
  Unterhaltung.
- **„Claude: NOT authenticated“ bei `/health`** ist mit OAuth-Token ein
  Fehlalarm: Diese Anzeige kennt nur API-Key und Login-Datei. Maßgeblich ist
  „Claude readiness ✓“ im Protokoll beim Start.
- **Nachrichten direkt nach dem Start:** Was ankommt, bevor im Protokoll
  `[bridge] ready` steht, erreicht den Gateway nicht. Dann einfach neu senden.
- **Identität wechseln:** Feld ändern und neu starten. Dann wird automatisch ein
  neuer Signing-Key erzeugt.
- **Fehler „Bootstrap fehlgeschlagen“:** Meist ein falscher Inkbox-API-Key oder
  ein Key ohne Zugriff auf die angegebene Identität. Details stehen im JSON
  darüber.
