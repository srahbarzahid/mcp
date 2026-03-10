from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('doctor', 'Doctor'),
        ('patient', 'Patient'),
        ('pharmacist', 'Pharmacist'),
        ('lab_tech', 'Lab Technician'),
    )
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='patient')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.username

# ... existing models (Department, Doctor, Patient, Ward, Bed, Appointment, Billing, Prescription)

class Medicine(models.Model):
    name = models.CharField(max_length=100)
    count = models.PositiveIntegerField(help_text="Current remaining stock")
    sold_count = models.PositiveIntegerField(default=0, help_text="Total units dispensed/sold")
    manufacture_date = models.DateField()
    expiry_date = models.DateField()
    company_name = models.CharField(max_length=150)
    storage_block = models.CharField(max_length=50, help_text="Where it's stored, e.g., 'A-10'")

    def __str__(self):
        return f"{self.name} - Stock: {self.count}"

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Doctor(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    specialization = models.CharField(max_length=100)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_available = models.BooleanField(default=True)
    bio = models.TextField(blank=True, null=True, help_text="Doctor's professional biography and description.")

    def __str__(self):
        return f"Dr. {self.user.full_name or self.user.username} ({self.specialization})"

class Patient(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    date_of_birth = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=5, blank=True, null=True)
    medical_history = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Patient: {self.user.full_name or self.user.username}"

class Ward(models.Model):
    WARD_TYPES = (
        ('general', 'General'),
        ('icu', 'ICU'),
        ('emergency', 'Emergency'),
        ('maternity', 'Maternity'),
        ('private', 'Private Room'),
    )
    name = models.CharField(max_length=50)
    ward_type = models.CharField(max_length=15, choices=WARD_TYPES)
    total_beds = models.PositiveIntegerField(default=10)

    def __str__(self):
        return f"{self.name} ({self.get_ward_type_display()})"

class Bed(models.Model):
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE)
    bed_number = models.CharField(max_length=10)
    is_occupied = models.BooleanField(default=False)
    current_patient = models.OneToOneField(Patient, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_bed')

    class Meta:
        unique_together = ('ward', 'bed_number')

    def __str__(self):
        status = "Occupied" if self.is_occupied else "Available"
        return f"Bed {self.bed_number} - {self.ward.name} ({status})"

class Appointment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    date = models.DateField()
    time = models.TimeField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    token_number = models.PositiveIntegerField(null=True, blank=True, help_text="Sequential token number for the doctor on this date")
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.patient.user.username} with {self.doctor} on {self.date} at {self.time}"

class Billing(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    )
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='bills')
    appointment = models.OneToOneField(Appointment, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    date_issued = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        display_name = self.patient.user.full_name or self.patient.user.username
        return f"Bill for {display_name} - ${self.amount} ({self.get_status_display()})"

class Prescription(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='prescriptions')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='prescriptions')
    appointment = models.OneToOneField(Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='prescription')
    date_created = models.DateTimeField(auto_now_add=True)
    medicines = models.JSONField(default=list, help_text="List of medicines, e.g., [{'name': 'Paracetamol', 'dosage': '500mg', 'quantity': 1}]")
    notes = models.TextField(blank=True, null=True)
    is_dispensed = models.BooleanField(default=False, help_text="Whether medicines have been dispensed by the pharmacist")

    def __str__(self):
        p_name = self.patient.user.full_name or self.patient.user.username
        d_name = self.doctor.user.full_name or self.doctor.user.username
        return f"Prescription for {p_name} by Dr. {d_name} on {self.date_created.date()}"

class LabTest(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Name of the test, e.g., LTSI, Blood Count")
    description = models.TextField(blank=True, null=True, help_text="Details about what the test measures")
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Cost of the test")

    def __str__(self):
        return f"{self.name} - ${self.cost}"

class LabRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='lab_requests')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='lab_requests')
    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_requests')
    tests = models.ManyToManyField(LabTest, related_name='requests')
    request_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True, help_text="Additional instructions for the lab technician")
    report_file = models.FileField(upload_to='lab_reports/', null=True, blank=True, help_text="Patient lab report in PDF format")

    def __str__(self):
        p_name = self.patient.user.full_name or self.patient.user.username
        return f"Lab Request for {p_name} on {self.request_date.date()} ({self.get_status_display()})"
