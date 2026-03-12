# Handover – Fahrstundenplaner

Diese Datei beschreibt, wie das Projekt lokal gestartet und auf Servern betrieben wird.

---

# Lokale Entwicklung

Python Umgebung erstellen

python -m venv .venv

aktivieren

Linux / macOS

source .venv/bin/activate

Windows

.venv\Scripts\activate

Dependencies installieren

pip install -r requirements.txt

Migrationen

python manage.py migrate

Superuser erstellen

python manage.py createsuperuser

Server starten

python manage.py runserver

---

# Login

/accounts/login/

---

# Rollen

## Admin / Staff

Startseite

/

Desktop Kalender

Funktionen

- Termine erstellen
- Stammdaten verwalten
- Einstellungen ändern

Bereiche

/students/
/instructors/
/vehicles/
/types/
/settings/

---

## Fahrlehrer

Startseite

/me/

Mobile Interface

Funktionen

- eigene Termine sehen
- Tagesansicht
- Wochenübersicht

API

/api/my/appointments/

---

# Wichtige Templates

Desktop

core/templates/core/calendar.html

Mobile

core/templates/mobile/month.html
core/templates/mobile/day.html
core/templates/mobile/details.html

Auth

core/templates/registration/login.html

---

# Datenbank

Lokale Entwicklung:

SQLite

Die Datei `db.sqlite3` im Repo dient **nur für lokale Entwicklung**.

Server:

Migrationen verwenden

python manage.py migrate

Die Server-Datenbank darf **nicht überschrieben werden**.

---

# APIs

/api/options/
/api/settings/
/api/appointments/
/api/my/appointments/
/api/unavailabilities/
/api/week-note/

---

# Aktueller stabiler Stand

fahrstundenplaner-live-baseline
Version v1.0.0
