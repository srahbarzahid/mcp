from django.test import TestCase
from django.utils import timezone
from datetime import date, time
from .models import CustomUser, Doctor, Patient, Appointment, Department
from .mcp_core import MCP_Core

class DoctorBookingLimitTest(TestCase):
    def setUp(self):
        # Create a department
        self.dept = Department.objects.create(name="Cardiology")
        
        # Create a doctor user
        self.doctor_user = CustomUser.objects.create_user(
            username='dr_smith', 
            password='password123', 
            role='doctor',
            first_name='John',
            last_name='Smith'
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user, 
            department=self.dept, 
            specialization='Cardiologist'
        )
        
        # Create a patient user
        self.patient_user = CustomUser.objects.create_user(
            username='patient_doe', 
            password='password123', 
            role='patient'
        )
        self.patient = Patient.objects.create(user=self.patient_user)

    def test_booking_limit_reaches_maximum(self):
        booking_date = date(2026, 5, 20)
        
        # 1. Create 70 existing appointments for this doctor on this date
        for i in range(70):
            Appointment.objects.create(
                patient=self.patient,
                doctor=self.doctor,
                date=booking_date,
                time=time(9, 0), # Simplified for testing, usually times would differ but the logic checks date
                status='confirmed'
            )
        
        # 2. Attempt to book the 71st appointment
        success, message = MCP_Core.book_appointment(
            self.patient_user,
            self.patient.pk,
            self.doctor.pk,
            booking_date,
            "10:00"
        )
        
        # 3. Verify it fails with the correct message
        self.assertFalse(success)
        self.assertEqual(message, "Booking closed: This doctor has reached the maximum limit of 70 bookings for this day.")

    def test_booking_under_limit_succeeds(self):
        booking_date = date(2026, 5, 21)
        
        # 1. Create 69 existing appointments
        for i in range(69):
            Appointment.objects.create(
                patient=self.patient,
                doctor=self.doctor,
                date=booking_date,
                time=time(9, 0),
                status='confirmed'
            )
            
        # 2. Attempt to book the 70th appointment
        success, result = MCP_Core.book_appointment(
            self.patient_user,
            self.patient.pk,
            self.doctor.pk,
            booking_date,
            "10:00"
        )
        
        # 3. Verify it succeeds
        self.assertTrue(success)
        self.assertIsInstance(result, Appointment)
