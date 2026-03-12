import json
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest, FileResponse, HttpResponseNotAllowed, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
import datetime
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie, csrf_protect
from django.views.decorators.cache import never_cache
from django.utils.dateparse import parse_datetime
from django.utils.dateparse import parse_date
from .models import WeekNote
from django.db import transaction
from django.utils import timezone
from django.db import models, connections
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.db import IntegrityError                             
from django.db.models.deletion import ProtectedError
from django.db.models import Q, Count, Sum, F, ExpressionWrapper, DurationField, Min, Max
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from .models import Appointment, Student, Vehicle, AppointmentType, AppSettings, Unavailability
from django.conf import settings
import sqlite3, os, io, shutil, time, tempfile, re

MOBILE_UA = (
    "iphone", "ipod", "ipad",      # iOS
    "android", "blackberry", "bb10",
    "webos", "iemobile", "opera mini",
    "mobile", "tablet", "silk"     # allgemein
)

_MOBILE_RE = re.compile(r"Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini", re.I)

def _is_admin(u): 
    return u.is_staff or u.is_superuser

@login_required
def post_login_redirect(request):
    """
    Nach erfolgreichem Login:
    - Staff/Superuser -> normale Startseite
    - sonst (Fahrlehrer) -> /me/
    Berücksichtigt ?next=... (falls vorhanden)
    """
    nxt = request.GET.get("next")
    if nxt:
        return redirect(nxt)
    if request.user.is_staff or request.user.is_superuser:
        return redirect("home")
    return redirect("instructor_home")

@login_required
@never_cache
def instructor_home(request):
    """
    Startseite nur für den eingeloggten Fahrlehrer (ohne Admin zu ändern).
    Rendern der mobilen Monatsseite, aber mit only_my=True,
    damit das Frontend /api/my/appointments/ nutzt.
    """
    if request.user.is_staff or request.user.is_superuser:
        return redirect("home")
    return render(request, "mobile/month.html", {"only_my": True})

@login_required
def my_appointments_api(request):
    """
    Liefert ausschließlich die Termine des eingeloggten Fahrlehrers.
    Zeitraumfilter (start/end) wie gewohnt, instructor wird serverseitig fest verdrahtet.
    """
    start = request.GET.get("start")
    end   = request.GET.get("end")
    qs = Appointment.objects.filter(instructor_id=request.user.id)
    if start and end:
        qs = qs.filter(start__lt=end, end__gt=start)

    # optionale Filter (zusätzlich)
    veh  = request.GET.get("vehicle")
    stud = request.GET.get("student")
    if veh and veh.isdigit():
        qs = qs.filter(vehicle_id=int(veh))
    if stud and stud.isdigit():
        qs = qs.filter(student_id=int(stud))

    return JsonResponse(events_to_fullcalendar(qs), safe=False)

def logout_any(request):
    # Erlaube GET und POST (damit 405 verschwindet, falls irgendwo noch ein <a href> existiert)
    if request.method in ("GET", "POST"):
        logout(request)
        return redirect("login")  # oder deine Startseite
    return HttpResponseNotAllowed(["GET", "POST"])

def is_mobile_request(request):
    ua = (request.META.get("HTTP_USER_AGENT") or "").lower()
    return any(k in ua for k in MOBILE_UA)

@login_required
@never_cache
def home_calendar(request):
    if not request.user.is_authenticated:
        # zurück nach Login, danach wieder auf die angeforderte URL
        return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")

    # ab hier: eingeloggte Nutzer
    if is_mobile_request(request):
        return redirect("m_month")   # oder m_day, wie du magst
    return calendar_view(request)

@csrf_protect
def students_page(request):
    """Liste + Formular für Fahrschüler (Neu/Bearbeiten/Löschen)."""
    active = "students"

    if request.method == "POST":
        action = request.POST.get("action")
        sid = request.POST.get("id") or None
        name  = (request.POST.get("name")  or "").strip()
        email = (request.POST.get("email") or "").strip() or None
        phone = (request.POST.get("phone") or "").strip() or None
        notes = (request.POST.get("notes") or "").strip() or ""

        if action in ("create", "update"):
            if not name:
                # Fehler zurück in die Seite geben
                ctx = {
                    "active": active,
                    "items": Student.objects.all().order_by("name"),
                    "edit": Student.objects.filter(pk=sid).first(),
                    "error": "Name ist erforderlich."
                }
                return render(request, "core/students.html", ctx)

            if sid:  # Update
                s = get_object_or_404(Student, pk=sid)
                s.name, s.email, s.phone, s.notes = name, email, phone, notes
                s.save()
            else:    # Create
                Student.objects.create(name=name, email=email, phone=phone, notes=notes)

            return redirect("students_page")

        if action == "delete":
            if sid:
                Student.objects.filter(pk=sid).delete()
            return redirect("students_page")
# GET
    edit_id = request.GET.get("edit")
    edit_obj = Student.objects.filter(pk=edit_id).first() if edit_id else None
    items = Student.objects.all().order_by("name")
    return render(request, "core/students.html", {"active": active, "items": items, "edit": edit_obj})


@login_required
def student_report_print(request, student_id: int):
    """Druckoptimierter Report für einen Fahrschüler (HTML → Browser-PDF).

    WICHTIG:
    - Kein Screenshot der UI (eigene Report-Seite)
    - Notizen des Schülers werden bewusst NICHT gedruckt (siehe Wunsch)
    """
    if not _is_admin(request.user):
        return HttpResponseForbidden("Nur Admin/Staff dürfen diesen Report sehen.")

    student = get_object_or_404(Student, pk=student_id)
    qs = (Appointment.objects
          .filter(student_id=student_id)
          .select_related('type', 'instructor', 'vehicle')
          .order_by('start'))

    now = timezone.now()
    all_list = list(qs)
    done = [a for a in all_list if a.end and a.end <= now]
    planned = [a for a in all_list if a not in done]

    def minutes(appt: Appointment) -> int:
        if not appt.start or not appt.end:
            return 0
        delta = appt.end - appt.start
        return max(0, int(round(delta.total_seconds() / 60)))

    def hm(total_minutes: int) -> str:
        h = total_minutes // 60
        m = total_minutes % 60
        return f"{h}h {m:02d}m"

    def row(a: Appointment) -> dict:
        m = minutes(a)
        return {
            'obj': a,
            'minutes': m,
            'hm': hm(m),
        }

    done_rows = [row(a) for a in done]
    planned_rows = [row(a) for a in planned]
    all_rows = [row(a) for a in all_list]

    done_min = sum(r['minutes'] for r in done_rows)
    planned_min = sum(r['minutes'] for r in planned_rows)
    total_min = done_min + planned_min

    ctx = {
        'student': student,
        'generated_at': now,
        'done_rows': done_rows,
        'planned_rows': planned_rows,
        'all_rows': all_rows,
        'done_ids': set(a.id for a in done),
        'done_count': len(done),
        'planned_count': len(planned),
        'total_count': len(done) + len(planned),
        'done_min': done_min,
        'planned_min': planned_min,
        'total_min': total_min,
        'done_hm': hm(done_min),
        'planned_hm': hm(planned_min),
        'total_hm': hm(total_min),
    }
    return render(request, 'core/student_report_print.html', ctx)

@login_required
@csrf_protect
def instructors_page(request):
    # Seite nur für Admins/Superuser
    if not _is_admin(request.user):
        return render(request, "core/instructors.html", {
            "active": "instructors",
            "items": User.objects.all().order_by("username"),
            "edit": None,
            "error": "Nur Admins dürfen Benutzer verwalten."
        })

    active = "instructors"

    if request.method == "POST":
        action = request.POST.get("action")
        uid = request.POST.get("id") or None

        username   = (request.POST.get("username")   or "").strip()
        first_name = (request.POST.get("first_name") or "").strip()
        last_name  = (request.POST.get("last_name")  or "").strip()
        email      = (request.POST.get("email")      or "").strip() or None
        password   = (request.POST.get("password")   or "").strip()

        # Flags
        want_staff = (request.POST.get("is_staff") == "on")
        can_touch_super = request.user.is_superuser
        want_super = can_touch_super and (request.POST.get("is_superuser") == "on")

        if action in ("create", "update"):
            if not username:
                return render(request, "core/instructors.html", {
                    "active": active,
                    "items": User.objects.all().order_by("username"),
                    "edit": User.objects.filter(pk=uid).first(),
                    "error": "Benutzername ist erforderlich."
                })

            try:
                if uid:
                    u = get_object_or_404(User, pk=uid)
                    u.username, u.first_name, u.last_name, u.email = username, first_name, last_name, email
                    if password:
                        u.set_password(password)

                    # Admin-Recht setzen/entziehen (Admins & Superuser dürfen das)
                    u.is_staff = want_staff

                    # Superuser umschalten NUR, wenn aktueller User Superuser ist
                    if can_touch_super:
                        if u.is_superuser and not want_super:
                            # nie den letzten Superuser entziehen
                            if User.objects.filter(is_superuser=True).exclude(pk=u.pk).count() == 0:
                                return render(request, "core/instructors.html", {
                                    "active": active,
                                    "items": User.objects.all().order_by("username"),
                                    "edit": u,
                                    "error": "Der letzte Superuser kann nicht entzogen werden."
                                })
                            u.is_superuser = False
                        elif not u.is_superuser and want_super:
                            u.is_superuser = True
                    # (Wenn aktueller User kein Superuser ist, ignorieren wir is_superuser still.)

                    u.save()

                else:
                    if not password:
                        return render(request, "core/instructors.html", {
                            "active": active,
                            "items": User.objects.all().order_by("username"),
                            "edit": None,
                            "error": "Passwort ist erforderlich."
                        })
                    u = User(username=username, first_name=first_name, last_name=last_name, email=email)
                    u.set_password(password)
                    u.is_staff = want_staff
                    u.is_superuser = want_super  # nur true, wenn can_touch_super
                    u.save()

                return redirect("instructors_page")

            except IntegrityError:
                return render(request, "core/instructors.html", {
                    "active": active,
                    "items": User.objects.all().order_by("username"),
                    "edit": User.objects.filter(pk=uid).first() if uid else None,
                    "error": "Benutzername ist bereits vergeben."
                })

        if action == "delete":
            if uid:
                u = get_object_or_404(User, pk=uid)
                if u.is_superuser:
                    return render(request, "core/instructors.html", {
                        "active": active,
                        "items": User.objects.all().order_by("username"),
                        "edit": None,
                        "error": "Ein Superuser kann hier nicht gelöscht werden."
                    })
                u.delete()
            return redirect("instructors_page")

    # GET
    edit_id = request.GET.get("edit")
    edit_obj = User.objects.filter(pk=edit_id).first() if edit_id else None
    items = User.objects.all().order_by("username")
    return render(request, "core/instructors.html", {"active": active, "items": items, "edit": edit_obj})


@csrf_protect
def vehicles_page(request):
    """Liste + Formular für Fahrzeuge (Neu/Bearbeiten/Löschen)."""
    active = "vehicles"

    if request.method == "POST":
        action = request.POST.get("action")
        vid = request.POST.get("id") or None
        label = (request.POST.get("label") or "").strip()
        plate = (request.POST.get("plate") or "").strip()
        # ⬇︎ NEU: nur erlaubte Werte
        allowed_trans = ("Schalter", "Automatik")
        transmission = (request.POST.get("transmission") or "Schalter").strip()
        if transmission not in allowed_trans:
            transmission = "Schalter"

        if action in ("create", "update"):
            if not (label and plate):
                ctx = {
                    "active": active,
                    "items": Vehicle.objects.all().order_by("label"),
                    "edit": Vehicle.objects.filter(pk=vid).first(),
                    "error": "Bezeichnung und Kennzeichen sind erforderlich."
                }
                return render(request, "core/vehicles.html", ctx)

            try:
                if vid:  # Update
                    v = get_object_or_404(Vehicle, pk=vid)
                    v.label, v.plate, v.transmission = label, plate, transmission
                    v.save()
                else:    # Create
                    Vehicle.objects.create(label=label, plate=plate, transmission=transmission)
                return redirect("vehicles_page")
            except IntegrityError:
                # z. B. doppeltes Kennzeichen (plate ist unique)
                ctx = {
                    "active": active,
                    "items": Vehicle.objects.all().order_by("label"),
                    "edit": Vehicle.objects.filter(pk=vid).first(),
                    "error": "Kennzeichen ist bereits vergeben."
                }
                return render(request, "core/vehicles.html", ctx)

        if action == "delete":
            if vid:
                try:
                    Vehicle.objects.filter(pk=vid).delete()
                except ProtectedError:
                    # durch on_delete=PROTECT in Appointment: Fahrzeug wird verwendet
                    ctx = {
                        "active": active,
                        "items": Vehicle.objects.all().order_by("label"),
                        "edit": Vehicle.objects.filter(pk=vid).first(),
                        "error": "Fahrzeug kann nicht gelöscht werden (in Terminen verwendet)."
                    }
                    return render(request, "core/vehicles.html", ctx)
            return redirect("vehicles_page")

    # GET
    edit_id = request.GET.get("edit")
    edit_obj = Vehicle.objects.filter(pk=edit_id).first() if edit_id else None
    items = Vehicle.objects.all().order_by("label")
    return render(request, "core/vehicles.html", {"active": active, "items": items, "edit": edit_obj})

@csrf_protect
def types_page(request):
    """Liste + Formular für Fahrttypen (Neu/Bearbeiten/Löschen)."""
    active = "types"

    if request.method == "POST":
        action = request.POST.get("action")
        tid = request.POST.get("id") or None
        name = (request.POST.get("name") or "").strip()
        color = (request.POST.get("color") or "#3b82f6").strip()
        try:
            duration = int(request.POST.get("duration") or 45)
        except ValueError:
            duration = 45

        if action in ("create", "update"):
            if not name:
                ctx = {
                    "active": active,
                    "items": AppointmentType.objects.all().order_by("name"),
                    "edit": AppointmentType.objects.filter(pk=tid).first(),
                    "error": "Name ist erforderlich."
                }
                return render(request, "core/types.html", ctx)

            # einfache Hex-Prüfung (#RRGGBB)
            import re
            if not re.fullmatch(r"#([0-9a-fA-F]{6})", color or ""):
                color = "#3b82f6"

            if tid:  # Update
                t = get_object_or_404(AppointmentType, pk=tid)
                t.name = name
                t.color = color
                t.default_duration_min = duration
                t.save()
            else:    # Create
                AppointmentType.objects.create(
                    name=name, color=color, default_duration_min=duration
                    )

            return redirect("types_page")

        if action == "delete":
            if tid:
                AppointmentType.objects.filter(pk=tid).delete()
            return redirect("types_page")

    # GET
    edit_id = request.GET.get("edit")
    edit_obj = AppointmentType.objects.filter(pk=edit_id).first() if edit_id else None
    items = AppointmentType.objects.all().order_by("name")
    return render(request, "core/types.html", {"active": active, "items": items, "edit": edit_obj})

@csrf_protect
def settings_page(request):
    active = "settings"
    s = get_settings_obj()

    db_engine = settings.DATABASES['default']['ENGINE']
    db_is_sqlite = db_engine.endswith('sqlite3')

    flash_ok = None
    flash_err = None

    if request.method == "POST":
        action = request.POST.get("action")

        # --- A) SQLite-Backup herunterladen ---
        if action == "download_sqlite":
            if not db_is_sqlite:
                flash_err = "DB-Backup über die Oberfläche ist nur mit SQLite möglich."
            else:
                try:
                    # Pfad zur SQLite-Datei
                    db_path = settings.DATABASES['default']['NAME']
                    if not os.path.isfile(db_path):
                        raise RuntimeError("SQLite-Datei nicht gefunden.")

                    # offene Verbindungen schließen, damit der Backup-Konsistenz hat
                    connections['default'].close()

                    # per sqlite3.Backup konsistent in eine temp-Datei sichern
                    ts = time.strftime("%Y%m%d-%H%M%S")
                    filename = f"db-backup-{ts}.sqlite3"
                    tmp_path = os.path.join(tempfile.gettempdir(), filename)

                    src = sqlite3.connect(db_path)
                    dst = sqlite3.connect(tmp_path)
                    with dst:
                        src.backup(dst)   # atomarer SQLite-Backup
                    src.close()
                    dst.close()

                    # Download streamen
                    return FileResponse(open(tmp_path, "rb"), as_attachment=True, filename=filename)
                except Exception as e:
                    flash_err = f"Backup fehlgeschlagen: {e}"

        # --- B) SQLite-Backup wiederherstellen (Upload) ---
        elif action == "restore_sqlite":
            if not db_is_sqlite:
                flash_err = "Wiederherstellung über die Oberfläche ist nur mit SQLite möglich."
            else:
                try:
                    up = request.FILES.get("dbfile")
                    if not up:
                        raise RuntimeError("Keine Datei ausgewählt.")

                    # Prüfheader: echte SQLite-Datei?
                    head = up.read(16)
                    up.seek(0)
                    if not head.startswith(b"SQLite format 3"):
                        raise RuntimeError("Ungültige Datei (kein SQLite-Backup).")

                    db_path = settings.DATABASES['default']['NAME']
                    db_dir  = os.path.dirname(db_path) or "."
                    os.makedirs(db_dir, exist_ok=True)

                    # aktuelle Verbindung schließen
                    connections['default'].close()

                    # aktuelle DB vorsichtshalber sichern
                    ts = time.strftime("%Y%m%d-%H%M%S")
                    if os.path.isfile(db_path):
                        backup_existing = f"{db_path}.pre-restore-{ts}.sqlite3"
                        shutil.copy2(db_path, backup_existing)

                    # Upload zuerst in temp-Datei schreiben …
                    with tempfile.NamedTemporaryFile(delete=False, dir=db_dir) as tf:
                        for chunk in up.chunks():
                            tf.write(chunk)
                        tmp_uploaded = tf.name

                    # … dann atomar ersetzen
                    shutil.move(tmp_uploaded, db_path)

                    flash_ok = "Datenbank wurde wiederhergestellt. Bitte die Seite aktualisieren."
                except Exception as e:
                    flash_err = f"Wiederherstellung fehlgeschlagen: {e}"

        # --- C) Deine bisherigen Einstellungs-Felder speichern (unverändert) ---
        else:
            def as_int(name, default):
                try:
                    return int(request.POST.get(name, default))
                except (TypeError, ValueError):
                    return default

            def as_time(name, default_hhmm):
                val = (request.POST.get(name) or default_hhmm)
                try:
                    return datetime.datetime.strptime(val, "%H:%M").time()
                except ValueError:
                    try:
                        return datetime.datetime.strptime(val, "%H:%M:%S").time()
                    except ValueError:
                        hh, mm = default_hhmm.split(":")
                        return datetime.time(int(hh), int(mm))

            s.company_name = (request.POST.get("company_name") or "Fahrstundenplaner").strip()
            s.week_start = as_int("week_start", 1)
            s.show_week_numbers = True if request.POST.get("show_week_numbers") == "on" else False

            s.slot_min_time = as_time("slot_min_time", "06:00")
            s.slot_max_time = as_time("slot_max_time", "21:00")
            s.slot_duration_min = as_int("slot_duration_min", 15)
            s.snap_duration_min = as_int("snap_duration_min", 15)
            s.default_new_duration_min = as_int("default_new_duration_min", 45)
            s.save()
            flash_ok = "Einstellungen gespeichert."

    ctx = {
        "active": active,
        "s": s,
        "db_engine": db_engine,
        "db_is_sqlite": db_is_sqlite,
        "flash_ok": flash_ok,
        "flash_err": flash_err,
    }
    return render(request, "core/settings.html", ctx)

def settings_api(request):
    s = get_settings_obj()
    return JsonResponse({
        "companyName": s.company_name,
        "firstDay": s.week_start,
        "weekNumbers": s.show_week_numbers,
        "slotMinTime": s.slot_min_time.strftime("%H:%M:%S"),
        "slotMaxTime": s.slot_max_time.strftime("%H:%M:%S"),
        "slotDuration": f"00:{s.slot_duration_min:02d}:00",
        "snapDuration": f"00:{s.snap_duration_min:02d}:00",
        "defaultNewDurationMin": s.default_new_duration_min,
    })


def get_settings_obj():
    s = AppSettings.objects.first()
    if not s:
        s = AppSettings.objects.create()
    return s

def _is_mobile(request):
    ua = request.META.get("HTTP_USER_AGENT", "")
    return bool(_MOBILE_RE.search(ua))

@ensure_csrf_cookie
def calendar_view(request):
    if _is_mobile(request):
        # Mobile landet auf Monats-Startseite
        return redirect("m_month")
    # Desktop: klassische Startseite rendern
    return render(request, "core/calendar.html", {})

# ---------- Hilfsfunktionen ----------
def events_to_fullcalendar(appts):
    tz = timezone.get_default_timezone()
    events = []
    for a in appts:
        start_local = timezone.localtime(a.start, tz)
        end_local   = timezone.localtime(a.end, tz)

        events.append({
            "id": a.id,
            # nur Fallback – das Frontend rendert selbst
            "title": a.student.name,
            "start": start_local.isoformat(),
            "end":   end_local.isoformat(),
            "backgroundColor": a.type.color,
            "extendedProps": {
                "instructorId": a.instructor_id,
                "instructorName": (a.instructor.get_full_name() or a.instructor.username),

                "studentId": a.student_id,
                "studentName": a.student.name,

                "vehicleId": a.vehicle_id,
                "vehicleLabel": f"{a.vehicle.label} ({a.vehicle.plate})",

                "typeId": a.type_id,
                "typeName": a.type.name,
                "typeColor": a.type.color,

                "notes": a.notes or "",

                "phone": a.student.phone if a.student else "",
            },
        })
    return events

def get_between(request):
    start = request.GET.get("start")
    end   = request.GET.get("end")
    qs = Appointment.objects.all()
    if start and end:
        qs = qs.filter(start__lt=end, end__gt=start)

    # optionale Filter
    instr = request.GET.get("instructor")
    veh   = request.GET.get("vehicle")
    stud  = request.GET.get("student")

    if instr and instr.isdigit():
        qs = qs.filter(instructor_id=int(instr))
    if veh and veh.isdigit():
        qs = qs.filter(vehicle_id=int(veh))
    if stud and stud.isdigit():
        qs = qs.filter(student_id=int(stud))

    return qs


def clean_and_save(instance: Appointment):
    instance.full_clean()
    instance.save()
    return instance

# ---------- Optionen + Termine ----------
def options_api(request):
    """Liefert Dropdown-Optionen für den Dialog."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    instructors = list(User.objects.all().values("id", "username", "first_name", "last_name", "email"))
    students = list(Student.objects.all().values("id", "name", "email", "phone"))
    vehicles = list(Vehicle.objects.all().values("id", "label", "plate", "transmission"))
    types = list(AppointmentType.objects.all().values("id", "name", "color", "default_duration_min"))

    instructors_fmt = [
        {"id": i["id"], "label": (f'{i["first_name"]} {i["last_name"]}'.strip() or i["username"] or i["email"])}
        for i in instructors
    ]
    students_fmt = [{"id": s["id"], "label": s["name"], "phone": s["phone"]} for s in students]
    vehicles_fmt = [{"id": v["id"], "label": f'{v["label"]} ({v["plate"]})'} for v in vehicles]

    return JsonResponse({
        "instructors": instructors_fmt,
        "students": students_fmt,
        "vehicles": vehicles_fmt,
        "types": types
    })

def appointments_api(request):
    if request.method == "GET":
        appts = get_between(request)
        return JsonResponse(events_to_fullcalendar(appts), safe=False)

    # ab hier NUR Admin:
    if not _is_admin(request.user):
        return JsonResponse({"ok": False, "error": "Nur Admin darf Termine ändern."}, status=403)

    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            start = parse_aware(data.get("start"))
            end   = parse_aware(data.get("end"))

            if not (start and end):
                return HttpResponseBadRequest("start/end fehlen")

            a = Appointment(
                start=start, end=end,
                instructor=User.objects.get(pk=data["instructorId"]),
                student=Student.objects.get(pk=data["studentId"]),
                vehicle=Vehicle.objects.get(pk=data["vehicleId"]),
                type=AppointmentType.objects.get(pk=data["typeId"]),
                notes=data.get("notes","")
            )
            clean_and_save(a)
            return JsonResponse({"ok": True, "id": a.id}, status=201)

        except (KeyError, ValueError) as e:
            return JsonResponse({"ok": False, "error": f"Ungültige Daten: {e}"}, status=400)
        except ValidationError as e:
            return JsonResponse({"ok": False, "error": "; ".join(e.messages)}, status=409)
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=400)

    return HttpResponseNotAllowed(["GET","POST"])

# Schüler-Auswertung
def student_report_api(request, student_id: int):
    try:
        student = Student.objects.get(pk=student_id)
    except Student.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Schüler nicht gefunden."}, status=404)

    def _parse(dt):
        from django.utils.dateparse import parse_datetime
        if not dt: return None
        d = parse_datetime(dt)
        if d and timezone.is_naive(d):
            d = timezone.make_aware(d, timezone.get_default_timezone())
        return d

    start = _parse(request.GET.get("start"))
    end   = _parse(request.GET.get("end"))

    base = Appointment.objects.filter(student=student)
    if start: base = base.filter(end__gt=start)
    if end:   base = base.filter(start__lt=end)

    # Dauer annotieren
    qs = base.annotate(
        dur=ExpressionWrapper(F("end") - F("start"), output_field=DurationField())
    )

    # Grundsummen
    agg = qs.aggregate(
        total_count=Count("id"),
        total_dur=Sum("dur"),
        last_dt=Max("start"),
    )
    # Nächster Termin separat ermitteln (nur Zukunft)
    next_agg = base.filter(start__gt=timezone.now()).aggregate(next_dt=Min("start"))

    by_type = (
        qs.values("type_id", "type__name", "type__color")
          .annotate(cnt=Count("id"), dur=Sum("dur"))
          .order_by("type__name")
    )
    by_instructor = (
        qs.values("instructor_id", "instructor__first_name", "instructor__last_name", "instructor__username")
          .annotate(cnt=Count("id"))
          .order_by("-cnt")
    )
    by_vehicle = (
        qs.values("vehicle_id", "vehicle__label", "vehicle__plate")
          .annotate(cnt=Count("id"))
          .order_by("-cnt")
    )

    def td_minutes(td): return int(td.total_seconds() // 60) if td else 0

    return JsonResponse({
        "ok": True,
        "student": {"id": student.id, "name": student.name, "email": student.email, "phone": student.phone},
        "total": {
            "count": agg["total_count"] or 0,
            "minutes": td_minutes(agg["total_dur"]),
            "last": agg["last_dt"].isoformat() if agg["last_dt"] else None,
            "next": next_agg["next_dt"].isoformat() if next_agg["next_dt"] else None,
        },
        "breakdown_by_type": [
            {
                "typeId": r["type_id"],
                "name": r["type__name"],
                "color": r["type__color"],
                "count": r["cnt"],
                "minutes": td_minutes(r["dur"]),
            } for r in by_type
        ],
        "instructors": [
            {
                "id": r["instructor_id"],
                "name": (f'{r["instructor__first_name"]} {r["instructor__last_name"]}'.strip() or r["instructor__username"]),
                "count": r["cnt"],
            } for r in by_instructor
        ],
        "vehicles": [
            {
                "id": r["vehicle_id"],
                "label": f'{r["vehicle__label"]} ({r["vehicle__plate"]})',
                "count": r["cnt"],
            } for r in by_vehicle
        ],
    })


def parse_aware(dt_str):
    dt = parse_datetime(dt_str)            # versteht "...Z" (UTC) und Offsets
    if dt is None:
        raise ValueError("Ungültiges Datum")
    if timezone.is_naive(dt):
        # Falls mal ohne Offset kommt: als Europe/Berlin interpretieren
        dt = timezone.make_aware(dt, timezone.get_default_timezone())
    return dt

def appointment_detail_api(request, pk: int):
    a = get_object_or_404(Appointment, pk=pk)

    # NEU: GET liefert die Daten für die Detailseite
    if request.method == "GET":
        tz = timezone.get_default_timezone()
        minutes = int((a.end - a.start).total_seconds() // 60) if (a.start and a.end) else None

        # "Noch geplant": Summe der geplanten Fahrzeit dieses Schülers ab diesem Termin (inkl. diesem Termin).
        # Wird in der mobilen Detailansicht angezeigt, um schnell zu sehen, wie viel Fahrzeit noch eingeplant ist.
        remaining_from = a.start
        remaining_minutes = 0
        if remaining_from:
            qs = Appointment.objects.filter(student_id=a.student_id, start__gte=remaining_from)
            qs = qs.annotate(dur=ExpressionWrapper(F("end") - F("start"), output_field=DurationField()))
            agg = qs.aggregate(total_dur=Sum("dur"))
            td = agg.get("total_dur")
            if td:
                remaining_minutes = int(td.total_seconds() // 60)
        return JsonResponse({
            "id": a.id,
            "start": timezone.localtime(a.start, tz).isoformat() if a.start else None,
            "end":   timezone.localtime(a.end, tz).isoformat()   if a.end   else None,
            "notes": a.notes or "",
            "minutes": minutes,

            "student_remaining_planned_minutes": remaining_minutes,

            "student": {
                "id": a.student_id,
                "name": a.student.name,
                "phone": a.student.phone,
            },
            "instructor": {
                "id": a.instructor_id,
                "name": (a.instructor.get_full_name() or a.instructor.username),
            },
            "vehicle": {
                "id": a.vehicle_id,
                "label": f"{a.vehicle.label} ({a.vehicle.plate})",
            },
            "type": {
                "id": a.type_id,
                "name": a.type.name,
                "color": a.type.color,
            },
        })

    if not _is_admin(request.user):
        return JsonResponse({"ok": False, "error": "Nur Admin darf Termine ändern."}, status=403)

    if request.method == "PATCH":
        try:
            data = json.loads(request.body.decode("utf-8"))
            if "start" in data: a.start = parse_aware(data["start"])
            if "end" in data:   a.end   = parse_aware(data["end"])
            if "instructorId" in data: a.instructor = User.objects.get(pk=data["instructorId"])
            if "studentId" in data: a.student = Student.objects.get(pk=data["studentId"])
            if "vehicleId" in data: a.vehicle = Vehicle.objects.get(pk=data["vehicleId"])
            if "typeId" in data: a.type = AppointmentType.objects.get(pk=data["typeId"])
            if "notes" in data: a.notes = data["notes"]
            clean_and_save(a)
            return JsonResponse({"ok": True})
        except ValidationError as e:
            return JsonResponse({"ok": False, "error": "; ".join(e.messages)}, status=409)
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=400)

    if request.method == "DELETE":
        a.delete()
        return JsonResponse({"ok": True})

    return HttpResponseNotAllowed(["PATCH","DELETE"])

# ---------- Stammdaten: Create-APIs ----------
@csrf_protect
def students_api(request):
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        name = (data.get("name") or "").strip()
        email = (data.get("email") or None)
        phone = (data.get("phone") or None)
        if not name:
            return JsonResponse({"ok": False, "error": "Name ist erforderlich."}, status=400)
        s = Student.objects.create(name=name, email=email, phone=phone)
        return JsonResponse({"ok": True, "id": s.id, "label": s.name})
    return HttpResponseNotAllowed(["POST"])

@csrf_protect
def vehicles_api(request):
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        label = (data.get("label") or "").strip()
        plate = (data.get("plate") or "").strip()
        transmission = (data.get("transmission") or "Schalter").strip().capitalize()
        if transmission not in ("Schalter", "Automatik"):
            transmission = "Schalter"

        if not (label and plate):
            return JsonResponse({"ok": False, "error": "Fahrzeugname und Kennzeichen sind erforderlich."}, status=400)
        v = Vehicle.objects.create(label=label, plate=plate, transmission=transmission)
        return JsonResponse({"ok": True, "id": v.id, "label": f"{v.label} ({v.plate})"})
    return HttpResponseNotAllowed(["POST"])

@csrf_protect
def types_api(request):
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        name = (data.get("name") or "").strip()
        color = (data.get("color") or "#3b82f6").strip()
        default_duration_min = int(data.get("default_duration_min") or 45)
        if not name:
            return JsonResponse({"ok": False, "error": "Name des Fahrttyps ist erforderlich."}, status=400)
        t = AppointmentType.objects.create(name=name, color=color, default_duration_min=default_duration_min)
        return JsonResponse({"ok": True, "id": t.id, "name": t.name})
    return HttpResponseNotAllowed(["POST"])

@csrf_protect
def instructors_api(request):
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        # Minimal: username + Passwort (Email optional)
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        email = (data.get("email") or "").strip() or None
        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()
        if not (username and password):
            return JsonResponse({"ok": False, "error": "Benutzername und Passwort sind erforderlich."}, status=400)
        u = User.objects.create(
            username=username, password=make_password(password),
            email=email, first_name=first_name, last_name=last_name
        )
        return JsonResponse({"ok": True, "id": u.id, "label": (f"{u.first_name} {u.last_name}".strip() or u.username)})
    return HttpResponseNotAllowed(["POST"])

def _parse_aware(dt_str):
    dt = parse_datetime(dt_str)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_default_timezone())
    return dt

@login_required
@require_http_methods(["GET", "PUT"])
@csrf_protect
def week_note_api(request, week_start_str):
    """
    GET  /api/week-note/<YYYY-MM-DD>/?instructor=<id>
         -> liefert spezifische Notiz; wenn nicht vorhanden, globale (scope = "specific"|"global")
    PUT  /api/week-note/<YYYY-MM-DD>/?instructor=<id>  { "text": "..." }
         -> speichert spezifisch (mit instructor) oder global (ohne)
    """
    d = parse_date(week_start_str)
    if not d:
        return JsonResponse({"ok": False, "error": "Ungültiges Datum"}, status=400)

    instr_param = request.GET.get("instructor")
    instr_obj = None
    if instr_param:
        if not instr_param.isdigit():
            return JsonResponse({"ok": False, "error": "Ungültiger Fahrlehrer."}, status=400)
        try:
            instr_obj = User.objects.get(pk=int(instr_param))
        except User.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Fahrlehrer nicht gefunden."}, status=404)

    if request.method == "GET":
        # 1) spezifische Notiz versuchen
        note = WeekNote.objects.filter(week_start=d, instructor=instr_obj).first()
        scope = "specific" if instr_obj else "global"

        # 2) Fallback auf global, wenn spezifisch nicht existiert
        if not note:
            note = WeekNote.objects.filter(week_start=d, instructor__isnull=True).first()
            if note and instr_obj:
                scope = "global"

        if not note:
            return JsonResponse({
                "ok": True,
                "week_start": d.isoformat(),
                "instructor": instr_obj.id if instr_obj else None,
                "text": "",
                "scope": scope,
            })

        return JsonResponse({
            "ok": True,
            "week_start": note.week_start.isoformat(),
            "instructor": note.instructor_id,
            "text": note.text or "",
            "scope": scope,
        })

    # PUT: speichern (für eingeloggte User erlaubt)
    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        data = {}
    text = (data.get("text") or "").strip()

    with transaction.atomic():
        note, _ = WeekNote.objects.get_or_create(
            week_start=d,
            instructor=instr_obj,   # None => global; User => spezifisch
            defaults={"text": text},
        )
        note.text = text
        note.save()

    return JsonResponse({
        "ok": True,
        "week_start": note.week_start.isoformat(),
        "instructor": note.instructor_id,
        "text": note.text or "",
        "scope": "specific" if instr_obj else "global",
    })

def unavailabilities_api(request):
    if request.method == "GET":
        start = request.GET.get("start")
        end   = request.GET.get("end")
        instr = request.GET.get("instructor")

        qs = Unavailability.objects.all()
        if start and end:
            s = _parse_aware(start)
            e = _parse_aware(end)
            if s and e:
                qs = qs.filter(start__lt=e, end__gt=s)  # Überschneidung

        if instr and instr.isdigit():
            qs = qs.filter(instructor_id=int(instr))

        tz = timezone.get_default_timezone()
        # color_hex = "#f59e0b"
        out = []
        for b in qs:
            out.append({
                "id": f"blk-{b.id}",
                "title": b.reason or "Frei/Urlaub",
                "start": timezone.localtime(b.start, tz).isoformat(),
                "end":   timezone.localtime(b.end, tz).isoformat(),
                "extendedProps": {
                    "kind": "block",
                    "instructorId": b.instructor_id,
                    "instructorName": (b.instructor.get_full_name() or b.instructor.username),
                    "reason": b.reason or "",
                    "typeName": "Frei/Urlaub"
                }
            })
        return JsonResponse(out, safe=False)
    
    if not _is_admin(request.user):
        return JsonResponse({"ok": False, "error": "Nur Admin darf Sperrzeiten ändern."}, status=403)

    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            s = _parse_aware(data.get("start"))
            e = _parse_aware(data.get("end"))
            if not s or not e:
                return JsonResponse({"ok": False, "error": "start/end fehlen oder ungültig"}, status=400)
            inst_id = int(data.get("instructorId"))
            reason = (data.get("reason") or "").strip()

            blk = Unavailability(start=s, end=e, instructor=User.objects.get(pk=inst_id), reason=reason)
            blk.full_clean()
            blk.save()
            return JsonResponse({"ok": True, "id": blk.id}, status=201)
        except ValidationError as ve:
            return JsonResponse({"ok": False, "error": "; ".join(ve.messages)}, status=409)
        except Exception as ex:
            return JsonResponse({"ok": False, "error": str(ex)}, status=400)

    return HttpResponseNotAllowed(["GET", "POST"])

@require_http_methods(["PATCH", "DELETE"])
@csrf_protect
def unavailability_detail_api(request, pk: int):
    blk = get_object_or_404(Unavailability, pk=pk)

    if not _is_admin(request.user):
        return JsonResponse({"ok": False, "error": "Nur Admin darf Sperrzeiten ändern."}, status=403)

    if request.method == "PATCH":
        try:
            data = json.loads(request.body.decode("utf-8"))
            if "start" in data: blk.start = _parse_aware(data["start"])
            if "end"   in data: blk.end   = _parse_aware(data["end"])
            if "instructorId" in data: blk.instructor = User.objects.get(pk=int(data["instructorId"]))
            if "reason" in data: blk.reason = (data["reason"] or "").strip()
            blk.full_clean()
            blk.save()
            return JsonResponse({"ok": True})
        except ValidationError as ve:
            return JsonResponse({"ok": False, "error": "; ".join(ve.messages)}, status=409)
        except Exception as ex:
            return JsonResponse({"ok": False, "error": str(ex)}, status=400)

    # DELETE
    blk.delete()
    return JsonResponse({"ok": True})

@login_required
@never_cache
def mobile_day(request):
    # optionales Datum aus ?d=YYYY-MM-DD
    initial_date = request.GET.get("d")
    only_my = request.user.is_authenticated and not (request.user.is_staff or request.user.is_superuser)
    return render(request, "mobile/day.html", {"initial_date": initial_date, "only_my": only_my})  # dein day.html

@login_required
@never_cache
def mobile_month(request):
    only_my = request.user.is_authenticated and not (request.user.is_staff or request.user.is_superuser)
    return render(request, "mobile/month.html", {"only_my": only_my})

@login_required
@never_cache
def mobile_details(request, pk):
    return render(request, "mobile/details.html", {"appt_id": pk})