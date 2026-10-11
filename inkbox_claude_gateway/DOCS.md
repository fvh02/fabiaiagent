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
| Apple-ID (Kalender) | Optional, siehe [Apple-Kalender](#apple-kalender). |
| App-spezifisches Passwort (Kalender) | Optional, siehe [Apple-Kalender](#apple-kalender). |
| Kalender für KI-Termine | Standard `Added by AI Agent`. Alle Termine, die Claude anlegt, landen dort. |
| Sprachnachrichten | Whisper-Modell für Sprachnachrichten, Standard `small`. `aus` schaltet es ab. |
| Arbeitsordner | Standard `/share/claude-workspace`. |
| Voice AI | Nur wenn die Identität eine Telefonnummer hat. |
| Claude-Modell | Optional, leer = Standard. |

**Speichern**, dann im Tab **Info** „Beim Booten starten“ und „Watchdog“
aktivieren und **Starten**.

## Apple-Kalender

Claude kann Termine in deinem Apple-Kalender (iCloud) anlegen, anzeigen und
löschen, z. B. per Nachricht „Trag mir morgen um 15 Uhr Zahnarzt ein“.

1. Auf [account.apple.com](https://account.apple.com) anmelden →
   **Anmeldung und Sicherheit → App-spezifische Passwörter** → neues Passwort
   erzeugen (Name z. B. „Home Assistant“). Dafür muss die
   Zwei-Faktor-Authentifizierung aktiv sein.
2. Im Add-on unter **Konfiguration** eintragen:
   - **Apple-ID (Kalender):** die E-Mail-Adresse deiner Apple-ID
   - **App-spezifisches Passwort:** das eben erzeugte Passwort (`xxxx-xxxx-xxxx-xxxx`),
     **nicht** dein normales Apple-Passwort
   - **Kalender für KI-Termine:** Name des Kalenders, in den alles kommt, was
     Claude anlegt (Standard `Added by AI Agent`). Den Kalender vorher in der
     Kalender-App anlegen, genau mit diesem Namen.
3. Speichern und neu starten. Im Protokoll steht
   `[inkbox] Apple-Kalender: aktiv (neue Termine in: Added by AI Agent)`.

Termine aus allen Kalendern kann Claude lesen und auf Nachfrage löschen. Neue
Termine landen immer im KI-Kalender, so erkennst du sie an dessen Farbe.

Das Kalender-Werkzeug darf Claude ohne Rückfrage benutzen. Alle anderen
Befehle fragen weiterhin per Nachricht nach. Zum Abschalten die beiden Felder
leeren. Das App-Passwort kannst du jederzeit auf account.apple.com widerrufen.

## Downloads

Claude kann das [Downloader-Add-on](https://github.com/fvh02/HA-downloader-Addon) steuern:
per Nachricht den Status abfragen („Wie weit sind meine Downloads?“) oder einen Link
schicken, der dann heruntergeladen wird.

1. Hier im Gateway unter **Konfiguration** die **Downloader-Adresse** prüfen:
   `http://<hostname>:8099`. Den Hostnamen zeigt der Downloader im Reiter **Info**
   (z. B. `4b225c51-downloader`). Die Vorgabe passt, wenn du den Downloader über
   `https://github.com/fvh02/HA-downloader-Addon` installiert hast. Eine Portfreigabe
   oder ein Token ist nicht nötig, beide Add-ons sprechen im internen Netz miteinander.
2. Speichern und neu starten. Im Protokoll steht `[inkbox] Downloader: aktiv (...)`.

Das `downloader`-Werkzeug darf Claude ohne Rückfrage benutzen. Links fügt Claude nur
hinzu, wenn du sie selbst schickst, nicht aus E-Mails oder weitergeleiteten Nachrichten.
Benachrichtigungen bei fertigen Downloads verschickt der Downloader selbst.

## Add-ons verwalten

Claude kann per Nachricht deine Home-Assistant-Add-ons verwalten, z. B.:

- „Welche Add-ons haben ein Update?“ / „Aktualisiere alle Add-ons“
- „Füge das Repository https://github.com/… hinzu“ – Claude sagt dir danach, welche Add-ons es anbietet
- „Installiere den Video-Downloader und starte ihn“
- „Entferne das Repository …“ (geht nur, wenn keine Add-ons daraus mehr installiert sind)

Anschauen darf Claude ohne Rückfrage. **Jede Änderung** (Repository hinzufügen/entfernen,
installieren, aktualisieren, deinstallieren, starten/stoppen) fragt dich vorher per Nachricht
(„1 = einmal erlauben, 2 = für diese Unterhaltung erlauben, 3 = ablehnen“). Claude handelt nur
auf deine eigene Nachricht hin, nie wegen einer E-Mail oder Webseite.

Dafür hat das Gateway Zugriff auf den Home-Assistant-Supervisor (Rolle „manager“). Home
Assistant zeigt deshalb eine niedrigere Sicherheitsbewertung an. Abschalten: Option
**Add-ons verwalten** aus.

Dieses Gateway selbst aktualisierst du am besten in Home Assistant: ein Update startet es neu
und würde Claude mitten in der Antwort unterbrechen.

## claude.ai-Connectoren

Mit dem OAuth-Token aus `claude setup-token` kann Claude nur antworten. Deine
auf claude.ai hinzugefügten Connectoren (z. B. Notion, Spotify) lädt Claude Code
nur mit einer **vollen claude.ai-Anmeldung**. Die erstellst du einmal auf einem
PC und gibst sie an das Add-on weiter:

1. **Samba share** installieren und starten (falls noch nicht geschehen).
2. Auf deinem PC Claude Code starten (`claude`), dort `/login` eingeben, dein
   Claude-Konto wählen und im Browser bestätigen. Danach `/exit`.
3. Die Anmeldedatei in die Home-Assistant-Freigabe kopieren und vom PC
   entfernen. Windows PowerShell:
   ```powershell
   New-Item -ItemType Directory -Force \\homeassistant.local\share\claude-login | Out-Null
   Move-Item "$env:USERPROFILE\.claude\.credentials.json" \\homeassistant.local\share\claude-login\ -Force
   ```
   Linux: `~/.claude/.credentials.json` nach `share/claude-login/` verschieben.
   macOS speichert die Anmeldung im Schlüsselbund, dort klappt das nicht.
4. Add-on neu starten. Im Protokoll steht
   `[inkbox] claude.ai-Anmeldung importiert.` und
   `Claude: claude.ai-Anmeldung (Connectoren verfügbar)`. Die Datei in der
   Freigabe wird dabei gelöscht.

Wichtig:
- Die Datei vom PC **verschieben**, nicht kopieren, und dort **nicht** `/logout`
  ausführen. Zwei Geräte mit derselben Anmeldung würden sich gegenseitig
  abmelden, und `/logout` widerruft sie. Willst du Claude Code am PC weiter
  nutzen, melde dich dort danach einfach neu mit `/login` an.
- Connector-Aufrufe fragen wie andere Werkzeuge zuerst per Nachricht nach.
  Mit `2`/`always` erlaubst du einen Connector für die laufende Unterhaltung.
- Zurück zum OAuth-Token: **claude.ai-Anmeldung verwenden** ausschalten und neu
  starten. Das löscht die Anmeldung im Add-on.

## Sprachnachrichten

Schickst du per iMessage eine Sprachnachricht, wird sie direkt auf deinem Home
Assistant mit Whisper in Text umgewandelt. Claude behandelt den Text so, als
hättest du ihn getippt, z. B. „Trag mir Freitag 18 Uhr Kino ein“. Die Audios
verlassen dein Gerät nicht.

- Beim ersten Start lädt das Add-on das Modell herunter. Das Protokoll zeigt
  danach `[whisper] {"ok": true, ...}`.
- Modelle: `tiny`/`base` sind schnell, aber ungenauer. `small` ist ein guter
  Kompromiss (ca. 500 MB, ~1 GB RAM). `medium`/`turbo` sind am genauesten, brauchen
  aber deutlich mehr RAM und Zeit.
- Die Modelle werden nicht in Home-Assistant-Backups gesichert und bei Bedarf
  neu geladen.

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
