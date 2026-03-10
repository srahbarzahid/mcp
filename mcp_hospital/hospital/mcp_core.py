from django.core.exceptions import PermissionDenied
from .models import CustomUser, Appointment, Bed, Patient, Doctor, Ward, Billing, Prescription, Medicine

class MCP_Core:
    """
    Multi-Agent Control Platform (MCP) Core Layer.
    All hospital operations are routed through this centralized intelligence.
    """
    
    @staticmethod
    def _check_permission(user: CustomUser, required_role: str):
        if not user.is_authenticated:
            raise PermissionDenied("Authentication required.")
        
        # Superusers are treated as admins regardless of their 'role' field
        if user.is_superuser:
            return True
            
        if required_role == 'doctor' and user.role not in ['doctor', 'pharmacist', 'lab_tech']:
            raise PermissionDenied("Clinical/Staff privileges required.")
            
        return True

    @classmethod
    def _auto_transition_statuses(cls):
        """
        AI-driven background check to update appointment statuses based on current time.
        Transitions Pending/Confirmed -> Completed if the time has passed.
        """
        from django.utils import timezone
        from datetime import datetime
        
        now = timezone.now()
        active_appts = Appointment.objects.filter(status__in=['pending', 'confirmed'])
        
        for appt in active_appts:
            # Combining date and time. timezone.now() is aware, so we make appt_datetime aware
            # using the current project timezone (Asia/Kolkata)
            from django.utils.timezone import get_current_timezone
            tz = get_current_timezone()
            appt_datetime = timezone.make_aware(datetime.combine(appt.date, appt.time), tz)
            
            if appt_datetime <= now:
                appt.status = 'completed'
                appt.save()

    @classmethod
    def get_appointments(cls, user: CustomUser, target_user_id=None, date_filter=None):
        """
        Intelligently fetches appointments and ensures statuses are globally up-to-date.
        """
        cls._check_permission(user, 'patient')
        
        # Run auto-transition to ensure consistency across the hospital
        # cls._auto_transition_statuses()
        
        base_query = Appointment.objects.all().order_by('date', 'time')
        
        if date_filter:
            base_query = base_query.filter(date=date_filter)
            
        if user.is_superuser:
            if target_user_id:
                return base_query.filter(patient__user__id=target_user_id) | \
                       base_query.filter(doctor__user__id=target_user_id)
            return base_query
            
        if user.role == 'doctor':
            return base_query.filter(doctor__user=user).select_related('prescription', 'patient__user')
        elif user.role == 'patient':
            return base_query.filter(patient__user=user).select_related('prescription', 'doctor__user')
            
        return Appointment.objects.none()

    @classmethod
    def book_appointment(cls, user: CustomUser, patient_id, doctor_id, date, time):
        """
        Intelligent scheduling logic with dynamic status assignment.
        """
        cls._check_permission(user, 'patient')
        
        # Ensure date and time are proper objects if they come in as strings
        from datetime import datetime, date as date_obj, time as time_obj
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        if isinstance(time, str):
            # Try parsing with and without seconds
            try:
                time = datetime.strptime(time, '%H:%M').time()
            except ValueError:
                time = datetime.strptime(time, '%H:%M:%S').time()

        # Conflict Check
        conflict = Appointment.objects.filter(
            doctor_id=doctor_id, 
            date=date, 
            time=time, 
            status__in=['pending', 'confirmed']
        ).exists()
        
        if conflict:
            return False, "Conflict: The doctor is already booked for this time slot."

        # Maximum Bookings Check (Limit: 70 per day)
        daily_bookings_count = Appointment.objects.filter(
            doctor_id=doctor_id,
            date=date,
            status__in=['pending', 'confirmed', 'completed']
        ).count()

        if daily_bookings_count >= 70:
            return False, "Booking closed: This doctor has reached the maximum limit of 70 bookings for this day."
            
        try:
            # Determine initial status based on time
            from django.utils import timezone
            now = timezone.now()
            appt_dt = timezone.make_aware(datetime.combine(date, time))
            
            # Determine initial status based on time
            initial_status = 'completed' if appt_dt <= now else 'confirmed'
            
            # Token number: max existing token + 1 for this doctor/date
            from django.db.models import Max
            last_token = Appointment.objects.filter(
                doctor_id=doctor_id, 
                date=date
            ).aggregate(Max('token_number'))['token_number__max'] or 0
            
            token_number = last_token + 1
            
            appointment = Appointment.objects.create(
                patient_id=patient_id,
                doctor_id=doctor_id,
                date=date,
                time=time,
                status=initial_status,
                token_number=token_number
            )
            
            # --- Automatic Billing Implementation ---
            from hospital.models import Billing
            Billing.objects.create(
                patient_id=patient_id,
                appointment=appointment,
                amount=500.00,  # Default consultation fee
                description=f"Consultation fee for appointment with Dr. {appointment.doctor}",
                status='pending'
            )
            
            return True, appointment
        except Exception as e:
            return False, str(e)
            
    @classmethod
    def auto_allocate_bed(cls, user: CustomUser, patient_id, ward_type):
        """
        Intelligent Bed Allocation: Finds the first available bed in the requested ward type.
        Supports re-allocation by freeing the patient's current bed first.
        """
        cls._check_permission(user, 'doctor')
        
        patient = Patient.objects.get(pk=patient_id)
        
        # If moving, free the current bed first
        if hasattr(patient, 'assigned_bed') and patient.assigned_bed:
            old_bed = patient.assigned_bed
            old_bed.is_occupied = False
            old_bed.current_patient = None
            old_bed.save()
            
        # Find available bed in the NEWly requested ward type
        available_bed = Bed.objects.filter(ward__ward_type=ward_type, is_occupied=False).first()
        
        if not available_bed:
            return False, f"No available beds in {ward_type.upper()} ward."
            
        # Complete Allocation
        available_bed.is_occupied = True
        available_bed.current_patient = patient
        available_bed.save()
        
        return True, available_bed
        
    @classmethod
    def discharge_patient(cls, user: CustomUser, patient_id):
        """
        Discharges a patient: Frees their assigned bed and clears the record.
        """
        cls._check_permission(user, 'doctor')
        
        try:
            from hospital.models import Patient
            patient = Patient.objects.get(pk=patient_id)
            
            if hasattr(patient, 'assigned_bed') and patient.assigned_bed:
                bed = patient.assigned_bed
                bed.is_occupied = False
                bed.current_patient = None
                bed.save()
                return True, "Patient discharged and bed is now free."
            
            return False, "Patient does not have an assigned bed."
        except Exception as e:
            return False, str(e)

    @classmethod
    def update_appointment_status(cls, user: CustomUser, appointment_id: int, new_status: str):
        """
        Allows doctors (assigned to the appointment) or admins to update status.
        Validates status against allowed choices.
        """
        # Basic permission check: requires at least doctor privileges
        cls._check_permission(user, 'doctor')
        
        try:
            appointment = Appointment.objects.get(pk=appointment_id)
            
            # Additional logic: Doctors can only update their OWN appointments
            if not user.is_superuser and appointment.doctor.user != user:
                raise PermissionDenied("You can only update your own appointments.")
            
            # Validate status
            valid_statuses = [choice[0] for choice in Appointment.STATUS_CHOICES]
            if new_status not in valid_statuses:
                return False, f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            
            appointment.status = new_status
            appointment.save()
            return True, f"Appointment status updated to {new_status}."
            
        except Appointment.DoesNotExist:
            return False, "Appointment not found."
        except Exception as e:
            return False, str(e)

    @classmethod
    def get_doctors(cls, user: CustomUser):
        """
        Retrieves all available doctors.
        """
        cls._check_permission(user, 'patient')
        return Doctor.objects.filter(is_available=True).select_related('user', 'department')

    @classmethod
    def get_billing(cls, user: CustomUser):
        """
        Retrieves billing information based on user role.
        """
        cls._check_permission(user, 'patient')
        
        if user.is_superuser:
            return Billing.objects.all().order_by('-date_issued')
        
        if user.role == 'patient':
            return Billing.objects.filter(patient__user=user).order_by('-date_issued')
        
        # Doctors don't typically see billing details in this HMS
        return Billing.objects.none()

    @classmethod
    def get_ward_status(cls, user: CustomUser):
        """
        Retrieves ward and bed occupancy status.
        """
        cls._check_permission(user, 'doctor') # Staff/Admins only
        
        return Ward.objects.all().prefetch_related('bed_set')

    @classmethod
    def create_prescription(cls, user: CustomUser, patient_id, appointment_id, medicines, notes):
        """
        Creates or updates a prescription for a patient.
        """
        cls._check_permission(user, 'doctor')
        
        try:
            doctor = Doctor.objects.get(user=user)
            # Use update_or_create to handle OneToOneField properly
            prescription, created = Prescription.objects.update_or_create(
                appointment_id=appointment_id,
                defaults={
                    'doctor': doctor,
                    'patient_id': patient_id,
                    'medicines': medicines,
                    'notes': notes
                }
            )
            return True, prescription
        except Exception as e:
            return False, str(e)

    @classmethod
    def get_patient_details(cls, user: CustomUser, patient_id):
        """
        Fetches detailed info about a patient for prescription/lab pages.
        Allows Doctors, Pharmacists, Lab Techs, and the Patient themselves.
        """
        try:
            patient = Patient.objects.get(pk=patient_id)
            
            # Access Control: Staff, Superuser, or the Patient themselves
            if user.role not in ['doctor', 'pharmacist', 'lab_tech'] and not user.is_superuser:
                if patient.user.id != user.id:
                    raise PermissionDenied("You do not have permission to view these patient details.")
            # Calculate age logic
            from datetime import date
            age = None
            if patient.date_of_birth:
                today = date.today()
                age = today.year - patient.date_of_birth.year - ((today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day))
            
            return {
                'name': patient.user.full_name or patient.user.username,
                'age': age or "N/A",
                'mobile': patient.user.phone_number or "N/A",
                'pk': patient.pk
            }
        except Patient.DoesNotExist:
            return None

    @classmethod
    def get_medicines(cls, user: CustomUser):
        """
        Retrieves the pharmacy inventory.
        """
        cls._check_permission(user, 'pharmacist')
        return Medicine.objects.all().order_by('name')

    @classmethod
    def add_medicine(cls, user: CustomUser, data):
        """
        Adds a new medicine to the inventory.
        """
        cls._check_permission(user, 'pharmacist')
        try:
            medicine = Medicine.objects.create(
                name=data['name'],
                count=data['count'],
                manufacture_date=data['manufacture_date'],
                expiry_date=data['expiry_date'],
                company_name=data['company_name'],
                storage_block=data['storage_block']
            )
            return True, medicine
        except Exception as e:
            return False, str(e)

    @classmethod
    def update_medicine(cls, user: CustomUser, medicine_id, data):
        """
        Updates an existing medicine's details or count.
        """
        cls._check_permission(user, 'pharmacist')
        try:
            medicine = Medicine.objects.get(pk=medicine_id)
            medicine.name = data.get('name', medicine.name)
            medicine.count = data.get('count', medicine.count)
            medicine.manufacture_date = data.get('manufacture_date', medicine.manufacture_date)
            medicine.expiry_date = data.get('expiry_date', medicine.expiry_date)
            medicine.company_name = data.get('company_name', medicine.company_name)
            medicine.storage_block = data.get('storage_block', medicine.storage_block)
            medicine.save()
            return True, medicine
        except Exception as e:
            return False, str(e)

    @classmethod
    def get_all_prescriptions(cls, user: CustomUser):
        """
        Allows pharmacists or admins to view all prescriptions generated by doctors.
        """
        # We'll allow pharmacists to view prescriptions
        if not user.is_superuser and user.role != 'pharmacist':
             raise PermissionDenied("Pharmacist privileges required.")
             
        return Prescription.objects.all().order_by('-date_created').select_related('doctor__user', 'patient__user')
