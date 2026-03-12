Deployment Guide – Fahrstundenplaner (Server A → Server B)
Ziel

Projekt läuft auf Server B exakt wie auf Server A:

Django + gunicorn (systemd)
nginx reverse proxy
Domain via Strato Subdomain A-Record
HTTPS via Let’s Encrypt/Certbot
Datenbank: SQLite

0) Voraussetzungen

Server B ist erreichbar per SSH

Projektordner von Server A wurde 1:1 nach Server B kopiert (inkl. db.sqlite3, .venv optional, staticfiles optional)

Gegeben:

Domain: planer.fahrschulesafe.com
Projektpfad: z.B. /srv/fahrstundenplaner

1) DNS Umstellung (Strato)
In Strato → Subdomain → DNS / A-Record:
planer.fahrschulesafe.com → IP von Server B
TTL (falls einstellbar): klein setzen (z.B. 300s), später wieder erhöhen.
Prüfen (vom lokalen PC oder irgendeinem Host):

nslookup planer.fahrschulesafe.com

Es sollte die neue IP anzeigen.

Hinweis: Solange DNS noch teils auf Server A zeigt, kann Certbot/HTTPS verwirrend sein. DNS zuerst sauber umstellen.

2) Server B Basis-Pakete installieren
sudo dnf update -y
sudo dnf install -y nginx python3 python3-pip

Certbot:
sudo dnf install -y certbot python3-certbot-nginx

3) Projektpfad & Rechte
Beispiel: /srv/fahrstundenplaner

3.1 System-User erstellen
sudo useradd --system --home /srv/fahrstundenplaner --shell /sbin/nologin fahrplaner

3.2 Ownership setzen
sudo chown -R fahrplaner:fahrplaner /srv/fahrstundenplaner

3.3 SQLite Schreibrechte sicherstellen
sudo chown fahrplaner:fahrplaner /srv/fahrstundenplaner/db.sqlite3

4) Python venv + Dependencies

Wenn .venv schon kopiert wurde, diesen Schritt ggf. skippen. Sicherer ist neu bauen:

cd /srv/fahrstundenplaner
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

5) Django Setup (SQLite)
cd /srv/fahrstundenplaner
source .venv/bin/activate

python manage.py migrate
python manage.py collectstatic --noinput


Optional: Superuser (falls neu):

python manage.py createsuperuser

6) gunicorn systemd Service (Fedora)
6.1 Service-Datei anlegen
sudo nano /etc/systemd/system/fahrstundenplaner.service


Inhalt:

[Unit]
Description=Gunicorn for Fahrstundenplaner
After=network.target

[Service]
Type=simple
User=fahrplaner
Group=fahrplaner
WorkingDirectory=/srv/fahrstundenplaner

# Optional: env-Datei (wenn du eine nutzt)
# EnvironmentFile=/srv/fahrstundenplaner/.env

ExecStart=/srv/fahrstundenplaner/.venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 fahrstundenplaner.wsgi:application

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target

6.2 Aktivieren & starten
sudo systemctl daemon-reload
sudo systemctl enable --now fahrstundenplaner
sudo systemctl status fahrstundenplaner --no-pager

6.3 Test: läuft gunicorn?
curl -I http://127.0.0.1:8000


Erwartet: 302 Found nach /accounts/login/?next=/ (oder 200 je nach Route).

Logs:

sudo journalctl -u fahrstundenplaner -n 200 --no-pager

7) nginx konfigurieren
7.1 nginx starten
sudo systemctl enable --now nginx
sudo systemctl status nginx --no-pager

7.2 Site config anlegen

Fedora nutzt meist automatisch /etc/nginx/conf.d/*.conf.

sudo nano /etc/nginx/conf.d/fahrstundenplaner.conf


HTTP-only (vor SSL)

server {
    listen 80;
    server_name planer.fahrschulesafe.com;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120;
    }
}


Test + Reload:

sudo nginx -t
sudo systemctl reload nginx


Test extern:

curl -I http://planer.fahrschulesafe.com

8) HTTPS mit Let’s Encrypt (Certbot)

Wenn DNS bereits auf Server B zeigt und Port 80 offen ist:

sudo certbot --nginx -d planer.fahrschulesafe.com


Certbot schreibt dann automatisch die SSL-Konfiguration.

Test:

curl -I https://planer.fahrschulesafe.com


Erwartet: 302 Found auf Login.

9) Firewall / Ports

Auf Hetzner Cloud: Firewall-Regeln prüfen:

TCP 80 offen
TCP 443 offen
SSH (22) offen

Auf Fedora ggf. firewalld:

sudo systemctl status firewalld --no-pager


Wenn aktiv:

sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload

10) SELinux (Fedora typisch)

Wenn jemals wieder 502 kommt obwohl gunicorn läuft:

getenforce


Wenn Enforcing, dann nginx Reverse-Proxy erlauben:

sudo setsebool -P httpd_can_network_connect on
sudo systemctl reload nginx

11) End-to-End Checks
11.1 Services
sudo systemctl status nginx --no-pager
sudo systemctl status fahrstundenplaner --no-pager

11.2 Sockets/Ports
sudo ss -lntp | grep ':80\|:443\|:8000'

11.3 Browser-Test

https://planer.fahrschulesafe.com → Login-Seite

Login als Admin → Kalender

Login als Fahrlehrer → Mobile /me/

Terminlisten + APIs funktionieren

12) Backup & Restore (SQLite) – Minimum
12.1 Regelmäßiges DB Backup

SQLite Datei:

/srv/fahrstundenplaner/db.sqlite3

Einfaches Backup (Datei kopieren, wenn Service kurz gestoppt wird):

sudo systemctl stop fahrstundenplaner
sudo cp /srv/fahrstundenplaner/db.sqlite3 /srv/fahrstundenplaner/backups/db.sqlite3.$(date +%F_%H%M)
sudo systemctl start fahrstundenplaner


Alternativ: Projekt hat bereits Backup/Restore UI in /settings/ (SQLite-only).

13) Troubleshooting (Quick)
502 Bad Gateway

gunicorn läuft?

curl -I http://127.0.0.1:8000
sudo systemctl status fahrstundenplaner --no-pager


nginx error log:

sudo tail -n 100 /var/log/nginx/error.log


SELinux:

getenforce
sudo setsebool -P httpd_can_network_connect on

SSL Include fehlt (options-ssl-nginx.conf)

Certbot war noch nicht gelaufen → sudo certbot --nginx -d planer.fahrschulesafe.com

14) Update-Workflow (später)

Wenn neue Version deployt:

Code aktualisieren (git pull / rsync / zip upload)
venv aktivieren + requirements (falls nötig)

migrate
collectstatic
gunicorn restart
nginx reload

cd /srv/fahrstundenplaner
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart fahrstundenplaner
sudo systemctl reload nginx