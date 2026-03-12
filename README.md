# Fahrstundenplaner

Webbasierte Django-Anwendung zur Verwaltung von Fahrstunden, Fahrschülern, Fahrlehrern und Fahrzeugen.

Die App kombiniert eine **Desktop-Kalenderoberfläche für Verwaltung** mit einer **mobil optimierten Oberfläche für Fahrlehrer**.

---

# Funktionen

## Kalender (Desktop)
- Wochen- / Tagesansicht mit **FullCalendar**
- Terminverwaltung (CRUD)
- Filter für:
  - Fahrlehrer
  - Fahrzeuge
  - Fahrschüler
- Anzeige von:
  - Minuten pro Tag
  - Wochen-Gesamtzeit
- Sperrzeiten / Urlaub als eigene Event-Art
- Wochen-Notizen (global oder fahrlehrerspezifisch)

---

## Mobile Oberfläche (Fahrlehrer)

### Monatsübersicht
- Kalenderübersicht mit Terminen
- Tage mit Terminen werden markiert

### Tagesansicht
Portrait:
- Liste aller Termine eines Tages

Landscape:
- Wochenübersicht (Mo–Sa)
- Termine als Zeitblöcke
- automatische Anzeige von freien Zeitfenstern

### Termin-Detail
- Fahrttyp
- Schüler
- Fahrzeug
- Dauer
- Telefonnummer
- Notizen

---

# Rollenmodell

| Rolle | Rechte |
|-----|-----|
| Benutzer | keine administrativen Rechte |
| Admin (`is_staff`) | volle Rechte innerhalb der App |
| Superuser (`is_superuser`) | vollständiger Systemzugriff |

### Sicherheitsregeln

- nur **Superuser** können Superuser erstellen
- letzter Superuser kann nicht entfernt werden
- Benutzer können sich **nicht selbst löschen**
- zusätzliche Passwortbestätigung beim Erstellen eines Superusers

---

# Stammdaten

Verwaltbare Bereiche:

- Fahrschüler
- Fahrlehrer / Benutzer
- Fahrzeuge
- Fahrttypen

---

# APIs

| Endpoint | Beschreibung |
|------|------|
| `/api/options/` | Dropdown-Daten |
| `/api/settings/` | App-Einstellungen |
| `/api/appointments/` | Termine |
| `/api/my/appointments/` | Termine des eingeloggten Fahrlehrers |
| `/api/unavailabilities/` | Sperrzeiten |
| `/api/week-note/<date>/` | Wochen-Notizen |

---

# Technik

Backend

- Python
- Django
- SQLite (Development)
- Gunicorn
- Nginx

Frontend

- FullCalendar
- Chart.js
- Vanilla JavaScript
- Responsive Mobile Templates

---

# Entwicklung starten

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser

python manage.py runserver
```

Login:

```
/accounts/login/
```

---

# Projektstatus

Aktuelle stabile Basis:

```
fahrstundenplaner-live-baseline
Version: v1.0.0
```

Weitere technische Details siehe:

- `STATUS.md`
- `handover.md`
