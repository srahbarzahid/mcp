"""
URL configuration for mcp_hospital project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from hospital import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('signup/', views.signup, name='signup'),
    
    # Dashboards routed via MCP Core logic
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/patient/', views.patient_dashboard, name='patient_dashboard'),
    path('dashboard/doctor/', views.doctor_dashboard, name='doctor_dashboard'),
    path('dashboard/doctor/appointments/', views.all_doctor_appointments, name='all_doctor_appointments'),
    path('dashboard/doctor/export/', views.export_doctor_appointments_csv, name='export_doctor_appointments_csv'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('appointment/book/', views.book_appointment, name='book_appointment'),
    path('appointment/update-status/', views.update_appointment_status, name='update_appointment_status'),
    path('billing/', views.view_bills, name='view_bills'),
    path('wards/', views.ward_status, name='ward_status'),
    path('allocate-bed/', views.allocate_bed, name='allocate_bed'),
    path('discharge-patient/', views.discharge_patient, name='discharge_patient'),
    path('prescription/add/<int:appointment_id>/', views.add_prescription, name='add_prescription'),
    path('lab/request/<int:appointment_id>/', views.request_lab_test, name='request_lab_test'),
    
    # Pharmacy URLs
    path('pharmacy/', views.pharmacy_dashboard, name='pharmacy_dashboard'),
    path('pharmacy/export/csv/', views.export_pharmacy_csv, name='export_pharmacy_csv'),
    path('pharmacy/export/pdf/', views.export_pharmacy_pdf, name='export_pharmacy_pdf'),
    path('pharmacy/medicine/add/', views.manage_medicine, name='add_medicine'),
    path('pharmacy/medicine/update/<int:medicine_id>/', views.manage_medicine, name='update_medicine'),
    path('pharmacy/prescriptions/', views.pharmacy_prescriptions, name='pharmacy_prescriptions'),
    path('pharmacy/prescription/<int:prescription_id>/', views.view_prescription_detail, name='prescription_detail'),
    
    # Lab URLs
    path('lab/', views.lab_dashboard, name='lab_dashboard'),
    path('lab/export/csv/', views.export_lab_csv, name='export_lab_csv'),
    path('lab/export/pdf/', views.export_lab_pdf, name='export_lab_pdf'),
    
    # Password Reset URLs
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),

    # Password Change URLs (Logged in users)
    path('password-change/', auth_views.PasswordChangeView.as_view(template_name='registration/password_change_form.html'), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), name='password_change_done'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
