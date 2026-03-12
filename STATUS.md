# Fahrstundenplaner – Status (Stand: 12.03.2026)

## Überblick

Django-App zur Verwaltung von Fahrstunden, Fahrschülern, Fahrlehrern und Fahrzeugen.

System kombiniert:

- Desktop Kalender für Verwaltung
- Mobile Oberfläche für Fahrlehrer

Unterscheidung:

Admin / Staff / Superuser → volle Rechte  
Fahrlehrer → nur eigene Termine

---

## Projekt

Repo: haki36/fahrstundenplaner

Branch: main

Stand (Version): v1.0.0

Baseline:
fahrstundenplaner-live-baseline

Letzter Commit:
(wird nach Commit ergänzt)

---

## Umgebung

Python: 3.10+

Framework: Django 4.2.5

Datenbank: SQLite

Die im Repo enthaltene `db.sqlite3` dient nur der lokalen Entwicklung.

Serverdatenbank wird ausschließlich über Migrationen aktualisiert.

---

## Implementierte Funktionen

### Authentifizierung

- Login
- Logout
- Password Change
- Rollenbasierte Redirects

Admin → Desktop Kalender  
Fahrlehrer → Mobile Oberfläche

---

### Desktop Kalender

FullCalendar Integration

Funktionen

- Terminverwaltung
- Filter
- Wochenübersicht
- Tagesübersicht

Anzeige

- Minuten pro Tag
- Wochen-Gesamtzeit

Zusatzfunktionen

- Sperrzeiten
- Wochen-Notizen

---

### Mobile Oberfläche

Monatsübersicht:
mobile/month.html

Tagesansicht:
mobile/day.html

Landscape Modus:

- Wochenübersicht
- Mo–Sa Raster
- freie Zeitblöcke sichtbar

---

### Termin Details

mobile/details.html

Anzeige:

- Fahrttyp
- Schüler
- Fahrzeug
- Dauer
- Notizen

---

## APIs

/api/options/
/api/settings/
/api/appointments/
/api/my/appointments/
/api/unavailabilities/
/api/week-note/
/api/students/<id>/report/

---

## Stammdaten

Verwaltbar:

- Fahrschüler
- Fahrlehrer
- Fahrzeuge
- Fahrttypen

Rollen:

- Benutzer
- Admin
- Superuser

Sicherheitsregeln:

- letzter Superuser geschützt
- Superuser können nur von Superuser erstellt werden
- Benutzer können sich nicht selbst löschen

---

## UX / Styling

Mobile Navigation

- Icons + Labels
- Bottom Navigation

Desktop

- Full Width Layout

Mobile

- responsive Layout
- Landscape Wochenmodus

---

## Bekannte Punkte / To-Do

- Mobile Wochen-Notiz noch nicht implementiert
- Automatische Tests fehlen
- kleinere Code-Aufräumarbeiten in views.py

---

## Roadmap

Mögliche Erweiterungen

- Reporting
- Konfliktprüfung
- bessere mobile Terminbearbeitung
- Multi-Fahrschul-Unterstützung

---

## Changelog

v1.0.0

Neue stabile Baseline

fahrstundenplaner-live-baseline
