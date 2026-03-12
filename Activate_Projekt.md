# Fahrstundenplaner

Kalender- und Terminverwaltung für Fahrschulen (Django + FullCalendar + Mobile-Views).

## Setup
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # Werte anpassen
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver