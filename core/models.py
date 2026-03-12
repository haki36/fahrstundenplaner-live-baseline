from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import datetime

class Student(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True, null=True, unique=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    def __str__(self): return self.name

class Vehicle(models.Model):
    label = models.CharField(max_length=120)
    plate = models.CharField(max_length=50, unique=True)
    transmission = models.CharField(max_length=50)  # Manuell/Automatik
    active = models.BooleanField(default=True)
    def __str__(self): return f"{self.label} ({self.plate})"

class AppointmentType(models.Model):
    name = models.CharField(max_length=80)
    color = models.CharField(max_length=7, default="#3b82f6")  # hex
    default_duration_min = models.PositiveIntegerField(default=45)
    def __str__(self): return self.name

# ---- Modell für Sperrzeiten  ----
class Unavailability(models.Model):
    start = models.DateTimeField()
    end   = models.DateTimeField()
    instructor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="unavailabilities")
    reason = models.CharField(max_length=200, blank=True, null=True)

    def clean(self):
        if self.end <= self.start:
            raise ValidationError({"end": "Endzeit muss nach Startzeit liegen."})

        overlap = models.Q(start__lt=self.end, end__gt=self.start)

        # Gegen andere Sperrzeiten (gleicher Fahrlehrer)
        qs_block = Unavailability.objects.filter(overlap, instructor_id=self.instructor_id)
        if self.pk: qs_block = qs_block.exclude(pk=self.pk)
        if qs_block.exists():
            raise ValidationError("Konflikt: In diesem Zeitraum existiert bereits eine Sperrzeit.")

        # Gegen Termine (gleicher Fahrlehrer)
        qs_appt = Appointment.objects.filter(overlap, instructor_id=self.instructor_id)
        if qs_appt.exists():
            raise ValidationError("Konflikt: Fahrlehrer hat bereits einen Termin in diesem Zeitraum.")

    def save(self, *a, **kw):
        self.full_clean()
        return super().save(*a, **kw)

    class Meta:
        indexes = [
            models.Index(fields=["start","end"]),
            models.Index(fields=["instructor","start"]),
        ]

    def __str__(self):
        return f"Block {self.instructor} {self.start:%Y-%m-%d %H:%M}"



class Appointment(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField()
    instructor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="appointments")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="appointments")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="appointments")
    type = models.ForeignKey(AppointmentType, on_delete=models.PROTECT)
    notes = models.TextField(blank=True, null=True)

    def clean(self):
        errors = {}

        if self.end <= self.start:
            errors["end"] = "Endzeit muss nach Startzeit liegen."

        if self.start and self.end:
            overlap = models.Q(start__lt=self.end, end__gt=self.start)
            qs = Appointment.objects.filter(overlap)
            if self.pk:
                qs = qs.exclude(pk=self.pk)

            if self.instructor_id and qs.filter(instructor_id=self.instructor_id).exists():
                errors["instructor"] = "Konflikt: Fahrlehrer ist bereits verplant."
            if self.vehicle_id and qs.filter(vehicle_id=self.vehicle_id).exists():
                errors["vehicle"] = "Konflikt: Fahrzeug ist bereits verplant."
            if self.student_id and qs.filter(student_id=self.student_id).exists():
                errors["student"] = "Konflikt: Schüler hat bereits einen Termin."

            # 3) Sperrzeiten beachten
            if self.instructor_id and Unavailability.objects.filter(
                instructor_id=self.instructor_id,
                start__lt=self.end,
                end__gt=self.start
            ).exists():
                errors["instructor"] = "Konflikt: Fahrlehrer ist in einer Sperrzeit (Frei/Urlaub)."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self): return f"{self.student} {self.start:%Y-%m-%d %H:%M}"
    
    class Meta:
        indexes = [
            models.Index(fields=["start", "end"]),
            models.Index(fields=["instructor", "start"]),
            models.Index(fields=["vehicle", "start"]),
            models.Index(fields=["student", "start"]),
        ]


# ===== Wochen-Notiz (freier Text pro Woche) =====
class WeekNote(models.Model):
    # Montag der Woche
    week_start = models.DateField()
    # optional zugeordneter Fahrlehrer; NULL = globale Notiz
    instructor = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name='week_notes'
    )
    text = models.TextField(blank=True, default='')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["week_start", "instructor"],
                name="uniq_weeknote_per_instructor"
            )
        ]
        indexes = [
            models.Index(fields=["week_start"]),
            models.Index(fields=["instructor", "week_start"]),
        ]

    def __str__(self):
        who = (self.instructor.get_full_name() or self.instructor.username) if self.instructor else "GLOBAL"
        return f"WeekNote {self.week_start} [{who}]"


class AppSettings(models.Model):
    company_name = models.CharField(max_length=100, default="fahrstundenplaner")

    # Kalender
    week_start = models.IntegerField(  # 0=Sonntag ... 6=Samstag
        default=1,
        choices=[(0,"Sonntag"),(1,"Montag"),(2,"Dienstag"),(3,"Mittwoch"),
                 (4,"Donnerstag"),(5,"Freitag"),(6,"Samstag")]
    )
    show_week_numbers = models.BooleanField(default=False)

    slot_min_time = models.TimeField(default=datetime.time(6, 0))   # 06:00
    slot_max_time = models.TimeField(default=datetime.time(21, 0))  # 21:00
    slot_duration_min = models.PositiveSmallIntegerField(default=15)   # Minuten
    snap_duration_min = models.PositiveSmallIntegerField(default=15)   # Minuten

    default_new_duration_min = models.PositiveSmallIntegerField(default=45)  # für „Neuer Termin“

    def __str__(self):
        return "AppSettings"