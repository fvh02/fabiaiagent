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

## eBay-Suche und Preisalarm

Claude sucht für dich auf eBay.de das günstigste Angebot, z. B.:

- „Such mir ein iPhone 15 128 GB, max. 450 €“
- „Gibt's die Sony WH-1000XM5 gebraucht unter 200 €?“
- „Sag mir Bescheid, wenn eine PS5 Slim unter 350 € auftaucht“ (Preisalarm)

Claude schickt dir die drei besten Angebote mit Gesamtpreis inkl. Versand, Zustand,
Verkäuferbewertung und Link. Zubehör, defekte Geräte und schlecht bewertete Verkäufer
filtert es vorher heraus. Auffällig billige Angebote markiert es als Warnung.
**Kaufen tust du selbst** über den Link. Claude kauft nie, bietet nie und fragt nie nach
Zahlungs- oder Anmeldedaten.

Einrichtung (einmalig, kostenlos):

1. Auf [developer.ebay.com](https://developer.ebay.com) mit deinem eBay-Konto ein
   Entwicklerkonto anlegen (Join). Die Freischaltung kann ein bis zwei Werktage dauern.
2. Unter **Application Keys** einen Namen eingeben und das **Production**-Keyset erstellen.
3. Falls eBay nach der „Marketplace Account Deletion Notification“ fragt:
   **Exempted** wählen („I do not persist eBay data“) und bestätigen.
4. Hier unter **Konfiguration** eintragen:
   - **eBay Client ID** = *App ID (Client ID)* aus dem Production-Keyset
   - **eBay Client Secret** = *Cert ID (Client Secret)*
   - **Deine Postleitzahl** (für genaue Versandkosten, optional)
   - **Deine Handynummer (Meldungen)** = deine Handynummer im Format `+49…` (für Preisalarme)
5. Speichern und neu starten. Im Protokoll steht `[inkbox] eBay: aktiv`.

Preisalarme prüft das Gateway alle 30 Minuten. Neue passende Angebote kommen per iMessage,
jedes nur einmal. „Welche Preisalarme habe ich?“ und „Lösch den PS5-Alarm“ gehen auch.

## Paketverfolgung

Der Assistent behält deine Pakete im Blick und meldet sich von selbst per iMessage, wenn ein
Paket **in Zustellung** ist („kommt heute“), **zur Abholung bereitliegt** (mit Adresse des
Paketshops), **zugestellt** wurde oder es ein **Problem** gibt. Sonst bleibt er still.

So kommen Pakete in die Liste:

- **Per Nachricht:** Sendungsnummer oder Tracking-Link schicken, gern mit Inhalt
  („Verfolg 00340434161234567890, das sind die AirPods“). Ein Screenshot der Versandbestätigung geht auch.
- **Per E-Mail, automatisch:** Versandbestätigungen an die E-Mail-Adresse deiner Inkbox-Identität
  weiterleiten – von Hand oder mit einer Weiterleitungsregel in deinem Postfach (z. B. für Mails
  von DHL, DPD, Hermes, GLS, UPS, Amazon mit „Versand“ oder „Sendung“ im Betreff). Der Assistent
  nimmt daraus nur die Sendungsnummer, antwortet nicht auf die Mail und schreibt dir kurz
  „📦 Neues Paket erkannt“.

Fragen kannst du jederzeit: „Wo ist mein Paket?“, „Kommt heute was?“, „Wo liegt das Kabel?“.
Zugestellte Pakete verschwinden nach drei Tagen von selbst aus der Liste.

Einrichtung:

1. **Handynummer:** Unter **Konfiguration** bei **Deine Handynummer (Meldungen)** eintragen
   (dasselbe Feld wie für die eBay-Preisalarme).
2. **Automatische Abfrage (empfohlen):** Auf [api.17track.net](https://api.17track.net) kostenlos
   registrieren, den API-Schlüssel kopieren und bei **Paketverfolgung – 17TRACK-Schlüssel**
   eintragen. Damit werden Pakete aller großen Paketdienste verfolgt. Wie viele Sendungsnummern
   der kostenlose Tarif pro Monat erlaubt, zeigt dir das 17TRACK-Dashboard.
3. **Optional DHL:** Auf [developer.dhl.com](https://developer.dhl.com) eine App mit der API
   „Shipment Tracking – Unified“ anlegen und den API-Key bei **Paketverfolgung – DHL-Schlüssel**
   eintragen. DHL-Pakete werden dann direkt bei DHL abgefragt.
4. Speichern und neu starten. Im Protokoll steht `[inkbox] Paketverfolgung: aktiv, Meldungen an …`.

Ohne Schlüssel merkt sich der Assistent die Pakete trotzdem und schaut bei Nachfrage auf der
Seite des Paketdiensts nach – automatische Meldungen gibt es dann nicht. Geprüft wird stündlich
zwischen 7 und 22 Uhr.

## Stundenplan (WebUntis)

Der Assistent meldet dir per iMessage **jede Änderung** in deinem WebUntis-Stundenplan –
Ausfall, Vertretung, Raumänderung, Sonderstunden – für heute und die nächsten 7 Tage, z. B.:

> 📚 Stundenplan:
> ❌ morgen 14.10. 2.–3. Std. Mathe: entfällt
> 🔁 morgen 14.10. 4. Std. Englisch: Raum B12 statt A04, „Aufgaben in Teams“

Findet eine gemeldete Stunde doch statt, kommt „✅ findet wieder normal statt“. Geprüft wird
alle 15 Minuten zwischen 6 und 22 Uhr; jede Änderung kommt nur einmal. Fragen gehen auch:
„Was hab ich morgen?“, „Fällt diese Woche was aus?“, „Wann ist Freitag Schluss?“.

Einrichtung unter **Konfiguration → Stundenpläne (WebUntis)**, ein Eintrag pro Stundenplan
(mehrere sind möglich):

- **name:** frei wählbar, z. B. `Fabian` – steht in den Meldungen, wenn es mehrere Pläne gibt
- **server:** Im Browser auf [webuntis.com](https://webuntis.com) die Schule suchen und die
  Login-Seite öffnen. Die Adresse aus der Adresszeile hier einfügen, z. B.
  `https://nessa.webuntis.com/WebUntis/?school=gym-musterstadt#/basic/login` – dann bleibt
  **school** leer.
- **username / password:** deine WebUntis-Anmeldung

Meldungen gehen an **Deine Handynummer (Meldungen)**. Speichern und neu starten; im Protokoll
steht pro Plan `[inkbox] Stundenplan Fabian: Anmeldung ok` oder der Fehler.

Hinweise: Es geht nur mit Untis-Benutzername und -Passwort, nicht mit „Mit Microsoft anmelden“.
Manche Schulen sperren den Zugriff für eigene Programme – dann steht das im Protokoll. Schlägt
die Anmeldung dreimal hintereinander fehl, bekommst du einmal eine Nachricht. Der Assistent liest
nur, er ändert nichts in WebUntis.

## 3D-Druck

Mit dem Add-on **3D-Druck** aus diesem Repository sucht Claude Modelle auf Printables, schickt
dir Bilder, slict für deinen Bambu Lab P1S und druckt nach deinem „Ja“. Status, Kamerabild,
Pause und Stopp gehen auch per Nachricht. Einrichtung siehe Doku des 3D-Druck-Add-ons; hier im
Gateway ist die Adresse (`druck_url`) schon voreingestellt.

## Krypto-Trader

Mit dem Add-on **Krypto-Trader** aus diesem Repository kannst du per Nachricht fragen, wie es
läuft („Wie steht der Krypto-Trader?“), dir Entscheidungen erklären lassen und das Trading
stoppen („Trading stopp“, „Not-Aus“). Weitermachen und Zusatz-Entscheidungen fragt Claude vorher
bei dir nach. Die Adresse (`krypto_url`) ist schon voreingestellt.

**Claude-Brücke (ab 0.12.0):** Der Trader nutzt für seine Entscheidungen die Claude-Anmeldung
des Gateways, damit du keinen zweiten Token brauchst. Dafür läuft im Gateway ein kleiner Dienst
(Port 8093, nur im internen Add-on-Netz), der reine Fragen ohne Werkzeuge außer Websuche an
Claude weitergibt. Er ist mit einem zufälligen Schlüssel geschützt, den das Gateway nach
`/share/claude-bridge/key` schreibt und nur Add-ons mit Zugriff auf `/share` lesen können.
Nach einem Gateway-Update erst das Gateway, dann den Trader neu starten.

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
