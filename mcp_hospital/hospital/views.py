from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .mcp_core import MCP_Core
from .forms import SignupForm
from .models import Patient, CustomUser, Prescription, Medicine

def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home.html')

def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.role = 'patient'  # Default role for signup
            user.save()
            
            # Create Patient profile
            Patient.objects.create(
                user=user,
                date_of_birth=form.cleaned_data['date_of_birth'],
                blood_group=form.cleaned_data['blood_group']
            )
            
            messages.success(request, "Account created successfully! Please log in.")
            return redirect('login')
    else:
        form = SignupForm()
    
    return render(request, 'signup.html', {'form': form})

@login_required
def dashboard(request):
    """
    Central router for dashboards based on user role or superuser status.
    """
    user = request.user
    if user.is_superuser:
        return redirect('admin_dashboard')
    elif user.role == 'doctor':
        return redirect('doctor_dashboard')
    elif user.role == 'patient':
        return redirect('patient_dashboard')
    elif user.role == 'pharmacist':
        return redirect('pharmacy_dashboard')
    elif user.role == 'lab_tech':
        return redirect('lab_dashboard')
    return redirect('home')

@login_required
def patient_dashboard(request):
    # Route all data fetching through the MCP Core
    try:
        appointments = MCP_Core.get_appointments(request.user)
    except Exception as e:
        appointments = None
        print(f"MCP Access Error: {e}")
        
    context = {
        'appointments': appointments,
        'patient': getattr(request.user, 'patient', None)
    }
    return render(request, 'patient_dashboard.html', context)

@login_required
def doctor_dashboard(request):
    # Route all data fetching through the MCP Core
    try:
        # User wants to see ONLY today's appointments
        today = timezone.localdate()
        appointments = MCP_Core.get_appointments(request.user, date_filter=today)
    except Exception as e:
        appointments = None
        print(f"MCP Access Error: {e}")
        
    context = {
        'appointments': appointments,
        'doctor': getattr(request.user, 'doctor', None)
    }
    return render(request, 'doctor_dashboard.html', context)

@login_required
def admin_dashboard(request):
    # Route all data fetching through the MCP Core
    try:
        appointments = MCP_Core.get_appointments(request.user)
    except Exception as e:
        appointments = None
        print(f"MCP Access Error: {e}")
        
    context = {
        'appointments': appointments,
    }
    return render(request, 'admin_dashboard.html', context)

@login_required
def book_appointment(request):
    """
    View for patients to book an appointment with a doctor.
    """
    if request.user.role != 'patient':
        return redirect('dashboard')

    error = None
    success_msg = None

    if request.method == 'POST':
        doctor_id = request.POST.get('doctor')
        date = request.POST.get('date')
        time = request.POST.get('time')
        
        # Use MCP Core to book the appointment
        success, result = MCP_Core.book_appointment(
            request.user, 
            request.user.patient.pk, 
            doctor_id, 
            date, 
            time
        )
        
        if success:
            success_msg = "Appointment booked successfully!"
        else:
            error = result

    # Fetch available doctors through the MCP
    doctors = MCP_Core.get_doctors(request.user)
    
    context = {
        'doctors': doctors,
        'error': error,
        'success_msg': success_msg
    }
    return render(request, 'book_appointment.html', context)

@login_required
def view_bills(request):
    """
    View for patients or admins to view billing information.
    """
    bills = MCP_Core.get_billing(request.user)
    return render(request, 'view_bills.html', {'bills': bills})

@login_required
def allocate_bed(request):
    """
    View for doctors to automatically allocate a bed for a patient.
    """
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        ward_type = request.POST.get('ward_type', 'general')
        
        from django.contrib import messages
        success, result = MCP_Core.auto_allocate_bed(request.user, patient_id, ward_type)
        
        if success:
            messages.success(request, f"Bed {result.bed_number} allocated successfully.")
        else:
            messages.error(request, f"Allocation failed: {result}")
        
    return redirect('dashboard')

@login_required
def discharge_patient(request):
    """
    View for doctors to discharge a patient and free their bed.
    """
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        
        from django.contrib import messages
        success, message = MCP_Core.discharge_patient(request.user, patient_id)
        
        if success:
            messages.success(request, message)
        else:
            messages.error(request, f"Discharge failed: {message}")
            
    return redirect('dashboard')

@login_required
def ward_status(request):
    """
    View for admins or doctors to view ward and bed occupancy.
    """
    wards = MCP_Core.get_ward_status(request.user)
    return render(request, 'ward_status.html', {'wards': wards})

@login_required
def update_appointment_status(request):
    """
    View to handle appointment status updates from the doctor dashboard.
    """
    if request.method == 'POST':
        appointment_id = request.POST.get('appointment_id')
        new_status = request.POST.get('new_status')
        
        success, message = MCP_Core.update_appointment_status(request.user, appointment_id, new_status)
        
    return redirect('dashboard')

@login_required
def request_lab_test(request, appointment_id):
    """
    Advanced view for doctors to request multiple lab tests for a patient.
    """
    if request.user.role != 'doctor':
        return redirect('dashboard')
        
    from .models import Appointment, LabTest, LabRequest
    try:
        appointment = Appointment.objects.get(pk=appointment_id)
        if not request.user.is_superuser and appointment.doctor.user != request.user:
            return redirect('dashboard')
    except Appointment.DoesNotExist:
        return redirect('dashboard')
        
    patient_details = MCP_Core.get_patient_details(request.user, appointment.patient.pk)
    available_tests = LabTest.objects.all()
    
    if request.method == 'POST':
        selected_tests = request.POST.getlist('lab_tests[]')
        notes = request.POST.get('notes')
        
        if selected_tests:
            lab_request = LabRequest.objects.create(
                patient=appointment.patient,
                doctor=appointment.doctor,
                appointment=appointment,
                notes=notes
            )
            lab_request.tests.add(*selected_tests)
            messages.success(request, f"Lab Request for {appointment.patient.user.full_name or appointment.patient.user.username} created successfully.")
            return redirect('dashboard')
        else:
            messages.error(request, "Please select at least one test to request.")
            
    return render(request, 'request_lab.html', {
        'appointment': appointment,
        'patient': patient_details,
        'available_tests': available_tests
    })

@login_required
def add_prescription(request, appointment_id):
    """
    Advanced view for doctors to add a prescription for a specific patient.
    """
    if request.user.role != 'doctor':
        return redirect('dashboard')
        
    from .models import Appointment
    try:
        appointment = Appointment.objects.get(pk=appointment_id)
        if not request.user.is_superuser and appointment.doctor.user != request.user:
            return redirect('dashboard')
    except Appointment.DoesNotExist:
        return redirect('dashboard')
        
    patient_details = MCP_Core.get_patient_details(request.user, appointment.patient.pk)
    
    # Check for existing prescription to support editing
    existing_prescription = getattr(appointment, 'prescription', None)
    
    if request.method == 'POST':
        medicine_names = request.POST.getlist('medicine_name[]')
        medicine_dosages = request.POST.getlist('medicine_dosage[]')
        medicine_quantities = request.POST.getlist('medicine_quantity[]')
        notes = request.POST.get('notes')
        
        medicines = []
        for i, (name, dosage) in enumerate(zip(medicine_names, medicine_dosages)):
            if name.strip():
                try:
                    qty = int(medicine_quantities[i]) if i < len(medicine_quantities) else 1
                except (ValueError, IndexError):
                    qty = 1
                medicines.append({'name': name, 'dosage': dosage, 'quantity': max(qty, 1)})
        
        success, result = MCP_Core.create_prescription(
            request.user, 
            appointment.patient.pk, 
            appointment.pk, 
            medicines, 
            notes
        )
        
        if success:
            from django.contrib import messages
            action = "updated" if existing_prescription else "added"
            messages.success(request, f"Prescription {action} successfully for {patient_details['name']}.")
            # Redirect to the all appointments view for better flow
            return redirect('all_doctor_appointments')
        else:
            error = result
    
    context = {
        'patient': patient_details,
        'appointment': appointment,
        'prescription': existing_prescription,
    }
    return render(request, 'add_prescription.html', context)

@login_required
def pharmacy_dashboard(request):
    """
    Dashboard for pharmacists to manage medicine inventory.
    """
    if request.user.role != 'pharmacist' and not request.user.is_superuser:
        return redirect('dashboard')
        
    medicines = MCP_Core.get_medicines(request.user)
    return render(request, 'pharmacy_dashboard.html', {'medicines': medicines})

@login_required
def manage_medicine(request, medicine_id=None):
    """
    View to add or update medicine details.
    """
    if request.user.role != 'pharmacist' and not request.user.is_superuser:
        return redirect('dashboard')
        
    medicine = None
    if medicine_id:
        from .models import Medicine
        medicine = Medicine.objects.get(pk=medicine_id)
        
    if request.method == 'POST':
        data = {
            'name': request.POST.get('name'),
            'count': request.POST.get('count'),
            'manufacture_date': request.POST.get('manufacture_date'),
            'expiry_date': request.POST.get('expiry_date'),
            'company_name': request.POST.get('company_name'),
            'storage_block': request.POST.get('storage_block'),
        }
        
        if medicine:
            success, result = MCP_Core.update_medicine(request.user, medicine_id, data)
        else:
            success, result = MCP_Core.add_medicine(request.user, data)
            
        if success:
            from django.contrib import messages
            messages.success(request, f"Medicine '{data['name']}' saved successfully.")
            return redirect('pharmacy_dashboard')
            
    return render(request, 'manage_medicine.html', {'medicine': medicine})

@login_required
def pharmacy_prescriptions(request):
    """
    View for pharmacists to see all doctor prescriptions.
    """
    if request.user.role != 'pharmacist' and not request.user.is_superuser:
        return redirect('dashboard')
        
    prescriptions = MCP_Core.get_all_prescriptions(request.user)
    return render(request, 'pharmacy_prescriptions.html', {'prescriptions': prescriptions})

@login_required
def view_prescription_detail(request, prescription_id):
    """
    Detailed view of a prescription for pharmacists.
    Allows dispensing medicines to update stock and sold counts.
    """
    prescription = Prescription.objects.get(pk=prescription_id)
    
    # Access control: Pharmacist, Superuser, Patient themselves, or the Doctor who generated it
    if request.user.role == 'patient' and prescription.patient.user.id != request.user.id:
        return redirect('dashboard')
    elif request.user.role not in ['pharmacist', 'patient', 'doctor'] and not request.user.is_superuser:
        return redirect('dashboard')
    elif request.user.role == 'doctor' and prescription.appointment.doctor.user.id != request.user.id:
        return redirect('dashboard')
    
    # Lazy import not needed if at top, but just being safe
    patient_details = MCP_Core.get_patient_details(request.user, prescription.patient.pk)
    
    if request.method == 'POST' and 'dispense' in request.POST:
        if prescription.is_dispensed:
            messages.warning(request, "This prescription has already been dispensed.")
            return redirect('pharmacy_prescriptions')
        
        dispensed_count = 0
        for med_data in prescription.medicines:
            med_name = med_data.get('name')
            quantity = med_data.get('quantity', 1)
            try:
                medicine = Medicine.objects.filter(name__iexact=med_name).first()
                if medicine and medicine.count >= quantity:
                    medicine.count -= quantity
                    medicine.sold_count += quantity
                    medicine.save()
                    dispensed_count += 1
                elif medicine and medicine.count > 0:
                    # Dispense whatever is available
                    available = medicine.count
                    medicine.sold_count += available
                    medicine.count = 0
                    medicine.save()
                    dispensed_count += 1
            except Exception as e:
                pass
        
        prescription.is_dispensed = True
        prescription.save()
                
        if dispensed_count > 0:
            messages.success(request, f"Successfully dispensed {dispensed_count} medicine(s) and updated inventory.")
        else:
            messages.warning(request, "No matching medicines found in inventory, or out of stock.")
            
        return redirect('pharmacy_prescriptions')
    
    return render(request, 'prescription_detail.html', {
        'prescription': prescription,
        'patient': patient_details
    })

@login_required
def lab_dashboard(request):
    """
    Advanced dashboard for lab technicians to view and manage lab requests.
    """
    if request.user.role != 'lab_tech' and not request.user.is_superuser:
        return redirect('dashboard')
        
    from .models import LabRequest
    from django.contrib import messages
    
    if request.method == 'POST':
        request_id = request.POST.get('request_id')
        new_status = request.POST.get('new_status')
        report_file = request.FILES.get('report_file')
        
        if request_id:
            try:
                lab_request = LabRequest.objects.get(pk=request_id)
                if new_status:
                    lab_request.status = new_status
                if report_file:
                    lab_request.report_file = report_file
                    lab_request.status = 'completed'
                lab_request.save()
                messages.success(request, f"Lab Request #{lab_request.pk} updated.")
            except LabRequest.DoesNotExist:
                messages.error(request, "Lab Request not found.")
        return redirect('lab_dashboard')
        
    # Get all lab requests, ordered by pending first, then by date
    lab_requests = LabRequest.objects.all().order_by('status', '-request_date')
        
    return render(request, 'lab_dashboard.html', {'lab_requests': lab_requests})

@login_required
def export_lab_csv(request):
    import csv
    from django.http import HttpResponse
    from .models import LabRequest
    
    if request.user.role != 'lab_tech' and not request.user.is_superuser:
        return redirect('dashboard')
        
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="lab_history.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Patient Name', 'Mobile Number', 'Age', 'Doctor Name', 'Tests', 'Status', 'Request Date'])
    
    requests = LabRequest.objects.filter(status='completed').order_by('-request_date')
    for req in requests:
        patient = req.patient
        age = "N/A"
        if patient.date_of_birth:
            import datetime
            today = datetime.date.today()
            age = today.year - patient.date_of_birth.year - ((today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day))
            
        tests_str = ", ".join([test.name for test in req.tests.all()])
        
        phone = patient.user.phone_number
        phone_display = f'="{phone}"' if phone else "N/A"
        date_display = f'="{req.request_date.strftime("%d %b %Y %H:%M")}"'
        
        writer.writerow([
            patient.user.full_name or patient.user.username,
            phone_display,
            age,
            req.doctor.user.full_name or req.doctor.user.username,
            tests_str,
            req.get_status_display(),
            date_display
        ])
        
    return response

@login_required
def export_lab_pdf(request):
    from django.http import HttpResponse
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from .models import LabRequest
    from io import BytesIO
    
    if request.user.role != 'lab_tech' and not request.user.is_superuser:
        return redirect('dashboard')
        
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=15,
        textColor=colors.HexColor('#2c3e50')
    )
    
    elements.append(Paragraph("AVM Hospital - Completed Lab Requests History", title_style))
    elements.append(Spacer(1, 12))
    
    data = [['Patient Name', 'Mobile', 'Age', 'Doctor Name', 'Tests', 'Date']]
    
    requests = LabRequest.objects.filter(status='completed').order_by('-request_date')
    for req in requests:
        patient = req.patient
        age = "N/A"
        if patient.date_of_birth:
            import datetime
            today = datetime.date.today()
            age = today.year - patient.date_of_birth.year - ((today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day))
            
        tests_str = ", ".join([test.name for test in req.tests.all()])
        
        data.append([
            patient.user.full_name or patient.user.username,
            patient.user.phone_number or "N/A",
            str(age),
            req.doctor.user.full_name or req.doctor.user.username,
            tests_str,
            req.request_date.strftime("%d %b %Y")
        ])
        
    table = Table(data, colWidths=[110, 80, 40, 110, 130, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e1e8ed')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="lab_history.pdf"'
    response.write(buffer.getvalue())
    buffer.close()
    
    return response

@login_required
def export_pharmacy_csv(request):
    """
    Exports the current Pharmacy Medicine Inventory to CSV.
    Forces string formatting for numeric fields to prevent Excel from applying scientific notation.
    """
    import csv
    from django.http import HttpResponse
    from .models import Medicine
    
    if request.user.role != 'pharmacist' and not request.user.is_superuser:
        return redirect('dashboard')
        
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="pharmacy_inventory.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Medicine Name', 'Company Name', 'Units Sold', 'Remaining Stock', 'Storage Location', 'Expiry Date'])
    
    medicines = Medicine.objects.all().order_by('name')
    for med in medicines:
        date_display = f'="{med.expiry_date.strftime("%d %b %Y")}"'
        
        writer.writerow([
            med.name,
            med.company_name,
            med.sold_count,
            med.count,
            med.storage_block,
            date_display
        ])
        
    return response

@login_required
def all_doctor_appointments(request):
    """
    Shows a comprehensive list of all appointments for the logged-in doctor.
    """
    if request.user.role != 'doctor':
        return redirect('dashboard')
        
    from .models import Doctor, Appointment
    from django.contrib import messages # Import messages for the error
    try:
        doctor = Doctor.objects.get(user=request.user)
        # Fetching all appointments for this doctor, optimized with related data
        appointments = Appointment.objects.filter(doctor=doctor)\
            .select_related('patient__user', 'patient__assigned_bed__ward', 'prescription')\
            .prefetch_related('lab_requests')\
            .order_by('-date', '-time')
    except Doctor.DoesNotExist:
        messages.error(request, "Doctor profile not found.")
        return redirect('dashboard')
        
    return render(request, 'all_appointments.html', {
        'appointments': appointments,
        'doctor': doctor
    })

@login_required
def export_doctor_appointments_csv(request):
    """
    Exports all appointments for the current doctor to an Excel-compatible CSV.
    """
    import csv
    from django.http import HttpResponse
    from .models import Doctor, Appointment
    
    if request.user.role != 'doctor':
        return redirect('dashboard')
        
    try:
        doctor = Doctor.objects.get(user=request.user)
        appointments = Appointment.objects.filter(doctor=doctor).order_by('-date', '-time')
    except Doctor.DoesNotExist:
        return redirect('dashboard')
        
    response = HttpResponse(content_type='text/csv')
    filename = f"appointments_{request.user.username}_{doctor.pk}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    # Header Row
    writer.writerow(['Token', 'Patient Name', 'Patient ID', 'Date', 'Time', 'Status', 'Ward/Bed'])
    
    for appt in appointments:
        bed_info = "No Bed Assigned"
        if appt.patient.assigned_bed:
            bed_info = f"{appt.patient.assigned_bed.ward.name}: {appt.patient.assigned_bed.bed_number}"
            
        status_display = appt.status
        if appt.status == 'completed': status_display = "Consulted"
        elif appt.status == 'cancelled': status_display = "Terminated"
        
        writer.writerow([
            appt.token_number or '--',
            appt.patient.user.full_name or appt.patient.user.username,
            appt.patient.pk,
            appt.date.strftime("%Y-%m-%d"),
            appt.time.strftime("%H:%M"),
            status_display.title(),
            bed_info
        ])
        
    return response

@login_required
def export_pharmacy_pdf(request):
    """
    Exports the current Pharmacy Medicine Inventory to a styled PDF.
    """
    from django.http import HttpResponse
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from .models import Medicine
    from io import BytesIO
    
    if request.user.role != 'pharmacist' and not request.user.is_superuser:
        return redirect('dashboard')
        
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=15,
        textColor=colors.HexColor('#2c3e50')
    )
    
    elements.append(Paragraph("AVM Hospital - Pharmacy Inventory Report", title_style))
    elements.append(Spacer(1, 12))
    
    data = [['Medicine Name', 'Company', 'Units Sold', 'Remaining Stock', 'Storage Location', 'Expiry Date']]
    
    medicines = Medicine.objects.all().order_by('name')
    for med in medicines:
        data.append([
            med.name,
            med.company_name,
            str(med.sold_count),
            str(med.count),
            med.storage_block,
            med.expiry_date.strftime("%d %b %Y")
        ])
        
    table = Table(data, colWidths=[130, 110, 60, 90, 90, 70])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e1e8ed')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="pharmacy_inventory.pdf"'
    response.write(buffer.getvalue())
    buffer.close()
    
    return response