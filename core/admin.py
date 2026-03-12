from django.contrib import admin
from .models import Student, Vehicle, AppointmentType, Appointment

admin.site.register(Student)
admin.site.register(Vehicle)
admin.site.register(AppointmentType)

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("start","end","student","instructor","vehicle","type")
    list_filter = ("instructor","vehicle","type")
