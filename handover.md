# Handover – Fahrstundenplaner

## Start – Lokal
1. Python/venv:
   - Python 3.10+ empfohlen
   - Virtuelle Umgebung anlegen/aktivieren:
     - `python -m venv .venv`
     - Linux/macOS: `source .venv/bin/activate`
     - Windows: `.venv\Scripts\activate`
2. Abhängigkeiten installieren:
   - `pip install -r requirements.txt`  *(Server-Version ist gepinnt: Django 4.2.5)*
3. Django Setup:
   - `python manage.py migrate`
   - Admin anlegen: `python manage.py createsuperuser`
   - Start: `python manage.py runserver`
4. Login unter `/accounts/login/` (oder `/login/` falls verwendet)

## Rollen/Navigation
- **Admin/Staff**:
  - Start: `"/"` → Desktop-Kalender (`core/calendar.html`)
  - Stammdaten: `/students/`, `/instructors/`, `/vehicles/`, `/types/`
  - Einstellungen: `/settings/` (inkl. SQLite-Backup/Restore)
- **Fahrlehrer (kein staff/su)**:
  - Start: `/me/` → `mobile/month.html`
  - Nur **eigene** Termine via `/api/my/appointments/`

## Wichtige Templates
- Desktop:
  - `core/templates/core/calendar.html`
- Mobile:
  - `core/templates/mobile/month.html`
  - `core/templates/mobile/day.html`  ← Portrait: Tagesliste, Landscape: Wochenraster (Mo–Sa)
  - `core/templates/mobile/details.html`
- Auth:
  - `core/templates/registration/login.html` (oder Standard)
  - `core/templates/core_auth/password_change_form.html`
  - `core/templates/core_auth/password_change_done.html`

## Desktop: volle Breite & Kurzname im Kalender
- Desktop-Templates (Kalender & Stammdaten) nutzen **volle Breite** (kein `max-width:1180px`).
  - Kalender: `core/templates/core/calendar.html` und `core/templates/core/base.html`
  - Stammdaten: `core/templates/core/students.html`, `instructors.html`, `vehicles.html`, `types.html`, `settings.html`
- Desktop-Kalender: In Event-Kacheln wird der **Vorname des Schülers abgekürzt** (Anzeige-only), z. B. `M. Mustermann`.
  - Ort: `core/templates/core/calendar.html` → `eventContent()`
  - Tooltip zeigt den vollen Namen; Datenbank bleibt unverändert.

## Schüler-Report (PDF-Export)
- Der Button **"Als PDF exportieren"** auf `/students/` öffnet eine **eigene, druckoptimierte Report-Seite**:
  - URL: `/students/<id>/report/`
  - Template: `core/templates/core/student_report_print.html`
  - View: `core.views.student_report_print`
- Inhalt des Reports:
  - Kopfbereich + Zusammenfassung (Minuten + Stunden)
  - Tabellen: "Absolvierte Fahrstunden" + "Geplante Fahrstunden" + "Alle Fahrstunden"
  - **Schülernotiz wird nicht gedruckt** (gewollt)
- Zugriff: nur Admin/Staff.

## Schülernotiz: bessere Sichtbarkeit
- Auf `/students/` wird die Schülernotiz zusätzlich **oberhalb der Fahrttypen-Liste** angezeigt (nur UI-Anzeige).
  - Ort: `core/templates/core/students.html` → Report-Rechts-Spalte (`#sr-notes-card`)

## Kern-Views (Auszug)
- `home_calendar`, `calendar_view`, `instructor_home`, `mobile_day`, `mobile_month`, `mobile_details`
- API:
  - `options_api`, `settings_api`
  - `appointments_api` (GET für alle, POST/PATCH/DEL nur Admin)
  - `appointment_detail_api` (GET/PATCH/DEL)
  - `my_appointments_api` (nur eingeloggter Fahrlehrer)
  - `unavailabilities_api` + `unavailability_detail_api`
  - `week_note_api` (global/spezifisch je nach `?instructor=`)

## URL-Mapping (Auszug)
- `/` → Desktop-Kalender (mit Mobile-Redirect in `calendar_view` wenn gewünscht)
- `/me/` → Mobile-Home (nur eigene Termine)
- `/m/` , `/m/day/`, `/m/a/<id>/` → mobile Ansichten
- `/api/…` → oben genannte APIs
- `/accounts/...` → Django-Auth
- `/login/`, `/logout/` → explizite Routen vorhanden


## Mobile Portrait: freie Zeitfenster (Gap-Blocks)
- Datei: `core/templates/mobile/day.html`
- Bereich: Funktion `loadDay()` (Portrait-Tagesliste)
- Zwischen zwei Terminen wird eine gestrichelte „Pause“-Karte eingefügt, wenn die Lücke **>= 5 Minuten** ist.
- Höhe ist leicht proportional zur Lücke (gedeckelt), damit man Pausen auch **visuell** erkennt.

## Mobile Landscape Woche
- Datei: `mobile/day.html`
- Erkennung: `matchMedia('(orientation: landscape)')` → zeigt `#weekGrid`, versteckt Tagesliste
- Spalten: **Mo–Sa** (Sonntag deaktiviert, siehe Kommentar im Code `SHOW_SUNDAY` Flag)
- **Frei/Pause-Blöcke**: werden **nur im Landscape-Wochenmodus** zwischen Terminen angezeigt (Gap ≥ 5 Min), um freie Zeit visuell zu sehen.
- **Nur eigene Termine** wenn `only_my` im Template-Kontext (View `mobile_day`) true ist

## Mobile Details: "Noch geplant"
- Datei: `mobile/details.html`
- Quelle: `appointment_detail_api` liefert `student_remaining_planned_minutes`
- Bedeutung: Summe der geplanten Fahrzeit dieses Schülers ab dem aktuell geöffneten Termin (inkl. diesem Termin)

## DB/Settings
- **Wichtig (Server-DB):** Die `db.sqlite3` im Repo ist nur für lokale Entwicklung/Tests. Auf dem Server wird die DB **nicht** überschrieben – Schema-Änderungen laufen ausschließlich über Migrationen (`makemigrations`, `migrate`).

- Model `AppSettings` liefert:
  - `week_start`, `show_week_numbers`, `slot_min_time`, `slot_max_time`, `slot_duration_min`, `snap_duration_min`, `default_new_duration_min`
- SQLite-Backup/Restore in `settings_page` (nur ENGINE=sqlite3)
  - Atomare Kopie via `sqlite3.Backup`
  - Datei-Header-Check beim Restore

## Was beim Weiterbauen wichtig ist
- **WeekNote in Mobile hinzufügen**:
  - API: `/api/week-note/<montag>/` + optional `?instructor=<id>`
  - Platzierungsvorschlag: kleines Panel oberhalb `#weekGrid`
- **Sonntag wieder aktivieren**:
  - In `day.html` `SHOW_SUNDAY = true` setzen; Spaltenzahl + Mapping anpassen.
- **Zeitachse/Slots**:
  - Aktuell 07–21 Uhr; an `SETTINGS.slotMinTime/slotMaxTime` ausrichten, wenn du’s, dynamisch willst.
- **Feinschliff**:
  - Lange Schülernamen umbrechen (`break-words` / `whitespace-normal`)
  - Doppelte `import`-Zeilen in `views.py` bereinigen

## Kontaktfragen / Edge Cases
- Termin-Konflikt → API liefert 409; Mobile zeigt Alert
- Sperrzeiten werden **nicht** auf Tag/Week-Summen angerechnet
- CSRF: Fetch-POSTs/PATCH/DELETE senden `X-CSRFToken`


## Mobile: Frei/Urlaub (Unavailabilities) in Landscape-Woche
- Datei: `core/templates/mobile/day.html` → Funktion `renderWeek()`
- Zusätzlich zu den **berechneten Pause/Frei-Lücken** werden echte Sperrzeiten aus der DB angezeigt.
- Quelle: `/api/unavailabilities/?start=...&end=...&instructor=<logged_in_user_id>`
- Wichtig: `INSTR_ID` wird nur gesetzt, wenn `only_my=true` (Fahrlehrer). Dadurch werden keine Sperrzeiten anderer Fahrlehrer geladen.
- Styling:
  - Gap (berechnet): wird **nicht geändert** (bestehender `gapEl.className` bleibt wie er ist).
  - Block (echt): `div.className = "rounded-xl border border-red-200 bg-red-50 ..."`
