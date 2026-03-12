# Fahrstundenplaner – Status (Stand: 02.02.2026)

## Überblick
Django-App zur Verwaltung von Fahrstunden (Kalender, Mobile-Ansicht, Stammdaten).
Unterscheidung: **Admin/Staff/SU** (volle CRUD-Rechte) vs. **Fahrlehrer** (nur eigene Termine; mobile Startseite).



## Projekt
- **Repo (GitHub, privat):** `haki36/fahrstundenplaner`
- **Branch:** `main`
- **Stand (Version):** `v1.0.6`
- **Letzter Commit:** *(nach dem Commit dieses Changes in GitHub Desktop eintragen)*

## Umgebung
- **Python:** 3.10+ empfohlen
- **Dependencies:** siehe `requirements.txt` (aktuell: `Django==4.2.5`)
- **Datenbank (Wichtig):** Die beigelegte `db.sqlite3` ist nur für lokale Entwicklung/Tests. Auf dem Server wird die DB **nicht** überschrieben – Schema-Änderungen laufen ausschließlich über `makemigrations`/`migrate`.
## Fertig / Implementiert
- **Auth & Rollen**
  - Login/Logout, PasswordChange (eigene Templates).
  - Post-Login-Redirect: Admin/Staff → Desktop-Kalender, Fahrlehrer → Mobile-Home.
  - Fahrlehrer sehen nur eigene Termine via `/api/my/appointments/`.

- **Kalender (Desktop)**
  - `core/templates/core/calendar.html` mit FullCalendar (Week/Day/List)
  - Filter: Fahrlehrer, Fahrzeug, Schüler (inkl. suchbarem Schüler-Combo).
  - Zusammenfassungen: Minuten/Tag, Wochen-Summe.
  - **Sperrzeiten/Urlaub** als eigene Event-Art (gestylte Kreuzkarte, ohne Summen).
  - **Wochen-Notizen** (global / fahrlehrer-spezifisch) inkl. Autosave.
  - Settings-API lädt FullCalendar-Parameter (Slot-Zeiten, Snap, Dauer etc.).

- **Mobile**
  - `mobile/month.html`: Monatsraster mit „Bullets“ für Tage mit Terminen, Bottom-Nav vereinheitlicht, Logout als Icon+Label vertically stacked.
  - `mobile/day.html`: Tagesliste (Portrait); **im Landscape** eine **Wochenübersicht (Mo–Sa)** mit Spalten und termin-Bubbles.
    - **NEU:** In **Landscape** werden zwischen Terminen **„Frei/Pause“-Blöcke** angezeigt (macht Lücken sofort sichtbar).
    - Sonntag ist ausgeblendet (mehr Platz).
    - Safe-Area / Padding am Seitenende berücksichtigt (Bottom-Nav überlappt nicht).
    - Nur eigene Termine für Fahrlehrer (only_my=true).
  - `mobile/details.html`: Termin-Detail (Typ-Badge, Fahrlehrer, Fahrzeug, Dauer, Telefon „tel:“-Link, Notizen).
    - **Neu:** "Noch geplant" (Summe der geplanten Fahrzeit dieses Schülers ab diesem Termin).

- **APIs & Daten**
  - `/api/options/` (Dropdown-Daten).
  - `/api/settings/` (App-Settings).
  - `/api/appointments/` (GET + Admin-POST/PATCH/DELETE).
  - `/api/appointments/<id>/` (Detail-GET + Admin-PATCH/DELETE).
  - `/api/my/appointments/` (nur eigene Termine für eingeloggten Fahrlehrer).
  - `/api/unavailabilities/` + `/api/unavailabilities/<id>/` (Sperrzeiten).
  - `/api/week-note/<YYYY-MM-DD>/?instructor=<id>` (global/spezifisch).
  - `/api/students/<id>/report/` (Auswertungen).

- **Stammdaten-Seiten**
  - Schüler, Fahrlehrer (mit Schutz: nicht-SU kann SU-Status nicht ändern; letzter SU geschützt), Fahrzeuge (Unique-Kennzeichen), Fahrttypen.

- **Einstellungen & DB-Wartung**
  - `settings_page`: UI + SQLite-Backup/Restore (atomar), nur wenn ENGINE=sqlite3.
  - AppSettings-Persistenz (Startwoche, Slot-Zeiten, Standarddauer etc.).

## UX/Styling
- Einheitliche Bottom-Navigation in Mobile (Icons + Label **unter** dem Icon).
- Material Symbols + Inter-Font in Mobile-Templates.
- FullCalendar Event-Rendering mit gut lesbaren Kärtchen, Kontrastprüfung.
- Sonntagsspalte **deaktiviert** in Landscape-Wochenraster von `day.html` (Kommentar vorhanden, leicht reaktivierbar).

## Bekannte Punkte / To-Do
- **Landscape Woche in `day.html`** zeigt Termine (gut) – **Wochennotiz-Text** der Woche wird noch **nicht** eingeblendet. (geplante Ergänzung: kompaktes Note-Panel oberhalb des Rasters)
- **Zeitachse links** in `day.html` (Landscape-Woche): umgesetzt als fixe Slot-Leiste (07–21 Uhr) und Sticky links; überprüfe auf sehr kleinen Geräten den Overflow.
- **Responsive Details**: Bei sehr langen Schülernamen ggf. weiche Trennung/Umbruch; aktuell mehrzeilig erlaubt, aber Styles prüfen.
- **Code-Aufräumung**: Ein paar doppelte Imports in `views.py` könnten bereinigt werden (mehrfaches `render`, `csrf_protect` etc.).
- **Tests**: keine automatischen Tests vorhanden – Wunschliste: Model-Validation, API-Smoke-Tests.
- **Sicherheit**: API-POST/PATCH/DELETE korrekt admin-geschützt; CSRF in Form-/Fetch-Requests gesetzt.

## Was noch geplant war (laut Verlauf)
- Optional: Wochennotiz im Mobile-Landscape einblenden.
- Optional: Sonntag wieder aktivierbar via Flag.
- Optional: bessere Event-Kollision-Meldungen in Mobile.
- Optional: Instructor-Quick-Switch auch in Mobile.


## Changelog (kurz)
- **v1.0.6**: Desktop-Layout nutzt volle Breite (ohne max-width-Limit); Desktop-Kalender zeigt Schülernamen in Event-Kacheln abgekürzt (Anzeige-only); Schülerseite: PDF-Export öffnet druckoptimierten Schüler-Report; Schülernotiz wird zusätzlich oberhalb der Fahrttypen-Liste angezeigt (nur UI, nicht im Report).
- **v1.0.4**: Mobile (Landscape-Woche) zeigt echte Frei/Urlaub-Slots (Unavailabilities) zusätzlich zu den berechneten Pausen – gefiltert auf den eingeloggten Fahrlehrer.
