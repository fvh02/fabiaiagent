# 3D-Druck

Dein Assistent findet per iMessage ein passendes 3D-Modell, schickt dir Bilder, slict es für
deinen **Bambu Lab P1S** und druckt es nach deinem „Ja“.

> Du: „Ich brauch einen Halter für meine AirPods an der Schreibtischkante“
> Assistent: schickt 3 Bilder (1, 2, 3) mit Namen
> Du: „Die 2“
> Assistent: „1 h 40 min, 23 g PLA. Starten?“
> Du: „Ja“ → der Druck startet, wenn er fertig ist kommt „✅ … ist fertig“ mit Kamerabild.

Außerdem jederzeit: „Wie weit ist der Drucker?“, „Schick mir ein Bild vom Drucker“,
„Pausiere/Stopp den Druck“.

## Voraussetzungen

- **Mini-PC** (amd64) als Home-Assistant-Server – der Slicer (OrcaSlicer) läuft im Add-on.
- **Inkbox Claude Gateway** ab 0.10.0 aus diesem Repository.
- Für Kamerabilder: die **Bambu-Lab-Integration** in Home Assistant.

## Drucker vorbereiten (einmalig)

Seit 2025 nimmt der Drucker Druckaufträge von anderen Programmen nur im LAN-Modus mit
Entwicklermodus an:

1. Am Drucker-Display: **Einstellungen → Netzwerk** (WLAN-Symbol) → **LAN Only Mode** einschalten.
2. Dort **Developer Mode** einschalten.
3. **IP-Adresse** und **Zugangscode** (Access Code, 8 Zeichen) notieren.
4. **Seriennummer**: Einstellungen → Gerät (oder in der Bambu-App unter Gerät).

Hinweis: Im LAN-Modus ist die Bambu-Cloud aus – Bambu Handy funktioniert dann nur noch im
Heimnetz. Bambu Studio/OrcaSlicer am PC können den Drucker im LAN weiterhin finden. In der
Bambu-Lab-Integration von Home Assistant den Drucker ggf. auf „Lokal“ umstellen.

## Einrichtung

1. Unter **Konfiguration** eintragen: Drucker-IP, Seriennummer, LAN-Zugangscode,
   Filament (meist PLA), Druckplatte (ab Werk Textured PEI), ggf. AMS und Fach.
2. **Inkbox API-Key** und **deine Handynummer** (`+49…`) eintragen – dorthin gehen
   Modellbilder, Kamerabilder und die Fertig-Meldung.
3. Add-on starten. Im Gateway ist die Adresse schon voreingestellt
   (`http://afcf546d-druck3d:8095`); Gateway neu starten, im Protokoll steht
   `[inkbox] 3D-Druck: aktiv`.

## Gut zu wissen

- Modelle kommen von **Printables** (kostenlose Modelle). Ein Link zu einer STL/3MF-Datei
  funktioniert auch.
- Slicen: Bambu-Profile für den P1S (0,4-mm-Düse), Qualität fein/standard/schnell,
  Stützen nur auf Wunsch. Die Ausrichtung des Modells bleibt wie vom Designer vorgesehen.
- Hat ein Modell viele Einzelteile, fragt der Assistent, welche gedruckt werden sollen.
- Gedruckt wird nur nach deiner ausdrücklichen Zustimmung in deiner eigenen Nachricht.
- Vorbereitete Aufträge werden nach 14 Tagen gelöscht.
