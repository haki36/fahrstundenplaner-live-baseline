SYSTEMD_BACKUP_SQLITE.md

# Systemd Daily Backup (SQLite) – Fahrstundenplaner

Dieses Dokument richtet auf Fedora (und generell systemd-basierte Linux-Systeme) einen **täglichen automatischen Backup-Job** für eine SQLite-Datenbank ein.

## Ziel
- Täglich ein konsistentes Backup von `db.sqlite3`
- Dateinamen nach Muster: `db.sqlite3.$(date +%F_%H%M)`
- Optional: Komprimierung (`.gz`)
- Optional: Rotation (z.B. 30 Tage aufbewahren)
- Ausführung über **systemd service + systemd timer** (professioneller als cron, mit Logs und "catch-up")

---

## Voraussetzungen
- Projektpfad (Beispiel): `/srv/fahrstundenplaner`
- SQLite Datei: `/srv/fahrstundenplaner/db.sqlite3`
- Backup-Ordner: `/srv/fahrstundenplaner/backups`
- `sqlite3` installiert

Installieren (Fedora):
```bash
sudo dnf install -y sqlite

Schritt 1: Backup-Verzeichnis anlegen
sudo mkdir -p /srv/fahrstundenplaner/backups

Schritt 2: Backup-Skript erstellen
sudo nano /usr/local/bin/fahrstundenplaner_backup.sh


Inhalt:

#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/srv/fahrstundenplaner"
DB="${APP_DIR}/db.sqlite3"
BACKUP_DIR="${APP_DIR}/backups"
TS="$(date +%F_%H%M)"
OUT="${BACKUP_DIR}/db.sqlite3.${TS}"

mkdir -p "${BACKUP_DIR}"

# Konsistentes SQLite-Backup (empfohlen, statt einfachem cp während Schreibzugriffen)
sqlite3 "${DB}" ".backup '${OUT}'"

# Optional: gzip spart Platz
gzip -f "${OUT}"

# Rotation: behalte Backups 30 Tage
find "${BACKUP_DIR}" -type f -name "db.sqlite3.*.gz" -mtime +30 -delete


Rechte setzen:

sudo chmod +x /usr/local/bin/fahrstundenplaner_backup.sh
sudo chown root:root /usr/local/bin/fahrstundenplaner_backup.sh


Wenn kein gzip: entferne die Zeile gzip -f "${OUT}" und passe die Rotation an:
-name "db.sqlite3.*" statt db.sqlite3.*.gz

Schritt 3: systemd Service (oneshot) erstellen
sudo nano /etc/systemd/system/fahrstundenplaner-backup.service


Inhalt:

[Unit]
Description=Backup SQLite DB for Fahrstundenplaner

[Service]
Type=oneshot
ExecStart=/usr/local/bin/fahrstundenplaner_backup.sh

Schritt 4: systemd Timer (täglich) erstellen
sudo nano /etc/systemd/system/fahrstundenplaner-backup.timer


Inhalt (täglich um 03:15 Uhr):

[Unit]
Description=Daily backup timer for Fahrstundenplaner

[Timer]
OnCalendar=*-*-* 03:15:00
Persistent=true

[Install]
WantedBy=timers.target


Wichtig:

Persistent=true sorgt dafür, dass der Timer nachholt, wenn der Server zur geplanten Zeit aus war.

Schritt 5: Aktivieren & Starten
sudo systemctl daemon-reload
sudo systemctl enable --now fahrstundenplaner-backup.timer

Schritt 6: Testlauf (manuell)
sudo systemctl start fahrstundenplaner-backup.service
ls -lah /srv/fahrstundenplaner/backups/


Sollten diese Dateien sehen:

db.sqlite3.2026-01-17_0315.gz

Schritt 7: Status & Logs

Timer anzeigen:

sudo systemctl list-timers | grep fahrstundenplaner
sudo systemctl status fahrstundenplaner-backup.timer --no-pager


Logs anzeigen:

sudo journalctl -u fahrstundenplaner-backup.service -n 50 --no-pager

Anpassungen
1) Backup-Zeit ändern

In /etc/systemd/system/fahrstundenplaner-backup.timer:

OnCalendar=*-*-* 03:15:00

Danach:

sudo systemctl daemon-reload
sudo systemctl restart fahrstundenplaner-backup.timer

2) Rotation ändern (z.B. 90 Tage)

Im Skript:

find "${BACKUP_DIR}" -type f -name "db.sqlite3.*.gz" -mtime +90 -delete

3) Ohne gzip

Entferne gzip -f "${OUT}"

Rotation anpassen:

find "${BACKUP_DIR}" -type f -name "db.sqlite3.*" -mtime +30 -delete

Troubleshooting
sqlite3: command not found
sudo dnf install -y sqlite

Backups werden nicht erstellt

Skript manuell ausführen:

sudo /usr/local/bin/fahrstundenplaner_backup.sh


Logs ansehen:

sudo journalctl -u fahrstundenplaner-backup.service -n 100 --no-pager

Rechteprobleme auf db.sqlite3

Stelle sicher, dass die DB lesbar ist:

sudo ls -la /srv/fahrstundenplaner/db.sqlite3


Falls nötig (vorsichtig einsetzen, Ownership bewusst anders will):

sudo chown fahrplaner:fahrplaner /srv/fahrstundenplaner/db.sqlite3

Hinweis zur Sicherheit

Backups enthalten personenbezogene Daten. Empfehlung:

Backup-Ordner mit restriktiven Rechten (z.B. nur root)