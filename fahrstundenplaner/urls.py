# Admin, Auth, URL-Helfer und meine Views reinholen
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from core import views as my_views

# zentrale URL-Routen der App
urlpatterns = [
    # Django-Admin
    path("admin/", admin.site.urls),

    # WICHTIG: Eigene Auth-Views (mit Custom-Templates) MÜSSEN vor dem include(...) kommen,
    # sonst überschreiben die Standard-Routen meine Templates.
    # Passwort ändern (Formular)
    path(
        "accounts/password_change/",
        auth_views.PasswordChangeView.as_view(
            template_name="core_auth/password_change_form.html"  # mein eigenes Template
        ),
        name="password_change",  # reverse("password_change")
    ),
    # Passwort geändert (Bestätigungsseite)
    path(
        "accounts/password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="core_auth/password_change_done.html"  # mein eigenes Template
        ),
        name="password_change_done",  # reverse("password_change_done")
    ),

    # Standard-Auth-URLs von Django (Login, Logout, Password Reset etc.)
    # Hinweis: Reihenfolge wichtig (meine Custom-Views oben drüber)!
    path("accounts/", include("django.contrib.auth.urls")),

    # ===== App-spezifische Routen =====

    # Startseite -> Kalenderübersicht (Home)
    path("", my_views.home_calendar, name="home"),

    # Nach dem Login ggf. zielgerichtet weiterleiten
    path("post-login/", my_views.post_login_redirect, name="post_login_redirect"),

    # "Mein Bereich" für Ausbilder/Instructor
    path("me/", my_views.instructor_home, name="instructor_home"),

    # Eigene Termine als API (für mich/aktuellen User)
    path("api/my/appointments/", my_views.my_appointments_api, name="my_appointments_api"),

    # Mobile Ansichten (Monatsübersicht)
    path("m/", my_views.mobile_month, name="m_month"),
    # Mobile Tagesansicht
    path("m/day/", my_views.mobile_day, name="m_day"),
    # Mobile Detailansicht zu einem Termin (per PK)
    path("m/a/<int:pk>/", my_views.mobile_details, name="m_details"),

    # Seiten für Stammdaten/Listen
    path("students/", my_views.students_page, name="students_page"),
    # Druckoptimierter Schüler-Report (HTML → Browser-PDF)
    path("students/<int:student_id>/report/", my_views.student_report_print, name="student_report_print"),
    path("instructors/", my_views.instructors_page, name="instructors_page"),
    path("vehicles/", my_views.vehicles_page, name="vehicles_page"),
    path("types/", my_views.types_page, name="types_page"),
    path("settings/", my_views.settings_page, name="settings_page"),

    # Eigene Login-/Logout-Routen (falls ich explizit diese URLs verwenden will)
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", my_views.logout_any, name="logout"),
    path("logout",  my_views.logout_any),

    # Optionen als API (z. B. für Frontend-Selects)
    path("api/options/", my_views.options_api, name="options_api"),

    # App-Einstellungen als API (nur wenn ich’s brauche)
    path("api/settings/", my_views.settings_api, name="settings_api"),

    # Termine (CRUD-ähnlich) als API
    path("api/appointments/", my_views.appointments_api, name="appointments_api"),
    path(
        "api/appointments/<int:pk>/",
        my_views.appointment_detail_api,
        name="appointment_detail_api",
    ),

    # Schülerbericht als API (generiert Bericht/Stats für einen Schüler)
    path(
        "api/students/<int:student_id>/report/",
        my_views.student_report_api,
        name="student_report_api",
    ),

    # Nicht-Verfügbarkeiten als API (z. B. Blocker/Urlaub)
    path("api/unavailabilities/", my_views.unavailabilities_api, name="unavailabilities_api"),
    path(
        "api/unavailabilities/<int:pk>/",
        my_views.unavailability_detail_api,
        name="unavailability_detail_api",
    ),

    # Wochen-Notizen als API (Basis: Startdatum der Woche als String)
    path(
        "api/week-note/<str:week_start_str>/", 
        my_views.week_note_api, 
        name="week_note_api"),
]
