from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Department, Doctor, Patient, Ward, Bed, Appointment, Billing, Prescription, Medicine, LabTest, LabRequest
from datetime import date

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'full_name', 'phone_number', 'age_display', 'role', 'is_staff']
    
    # Fieldsets for editing existing users
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('full_name', 'email', 'phone_number', 'address')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Role Information', {'fields': ('role',)}),
    )
    
    # Fieldsets for adding new users
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Personal info', {'fields': ('full_name', 'email', 'phone_number')}),
        ('Role Information', {'fields': ('role',)}),
    )

    def age_display(self, obj):
        if hasattr(obj, 'patient') and obj.patient.date_of_birth:
            today = date.today()
            dob = obj.patient.date_of_birth
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return "N/A"
    age_display.short_description = 'Age'

class DoctorAdmin(admin.ModelAdmin):
    list_display = ['get_name', 'specialization', 'consultation_fee', 'is_available']
    list_filter = ['specialization', 'is_available', 'department']
    search_fields = ['user__full_name', 'user__username', 'specialization']
    readonly_fields = ['full_name_display', 'mobile_number_display']
    
    fieldsets = (
        (None, {'fields': ('user', 'full_name_display', 'mobile_number_display')}),
        ('Professional Info', {'fields': ('department', 'specialization', 'consultation_fee', 'is_available', 'bio')}),
    )

    def full_name_display(self, obj):
        return obj.user.full_name or obj.user.username
    full_name_display.short_description = 'Full Name'

    def mobile_number_display(self, obj):
        return obj.user.phone_number or "N/A"
    mobile_number_display.short_description = 'Mobile Number'

    def get_name(self, obj):
        return obj.user.full_name or obj.user.username
    get_name.short_description = 'Doctor Name'

class PatientAdmin(admin.ModelAdmin):
    list_display = ['get_name', 'date_of_birth', 'blood_group', 'age_display']
    list_filter = ['blood_group']
    search_fields = ['user__full_name', 'user__username', 'blood_group']
    readonly_fields = ['full_name_display', 'mobile_number_display']
    
    fieldsets = (
        (None, {'fields': ('user', 'full_name_display', 'mobile_number_display')}),
        ('Medical Info', {'fields': ('date_of_birth', 'blood_group', 'medical_history')}),
    )

    def full_name_display(self, obj):
        return obj.user.full_name or obj.user.username
    full_name_display.short_description = 'Full Name'

    def mobile_number_display(self, obj):
        return obj.user.phone_number or "N/A"
    mobile_number_display.short_description = 'Mobile Number'

    def get_name(self, obj):
        return obj.user.full_name or obj.user.username
    get_name.short_description = 'Patient Name'

    def age_display(self, obj):
        if obj.date_of_birth:
            today = date.today()
            dob = obj.date_of_birth
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return "N/A"
    age_display.short_description = 'Age'

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Department)
admin.site.register(Doctor, DoctorAdmin)
admin.site.register(Patient, PatientAdmin)
admin.site.register(Ward)
admin.site.register(Bed)
admin.site.register(Appointment)
admin.site.register(Billing)
admin.site.register(Prescription)
admin.site.register(Medicine)
admin.site.register(LabTest)
admin.site.register(LabRequest)
