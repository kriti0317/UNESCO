import uuid
from django.db import models
from django.contrib.auth.models import User

class Agency(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active / Licensed'),
        ('EXPIRED', 'License Expired'),
        ('CANCELLED', 'License Cancelled / Suspended'),
    )

    name = models.CharField(max_length=255, db_index=True)
    license_number = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='ACTIVE')
    address = models.TextField(blank=True, default='')
    contact = models.CharField(max_length=200, blank=True, default='')
    source_url = models.URLField(default="https://foreignjob.dofe.gov.np")
    last_synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Agencies"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (License: {self.license_number or 'N/A'}) - {self.get_status_display()}"


class Consultancy(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    status = models.CharField(max_length=100, default='MANUALLY_CURATED')
    source_note = models.CharField(max_length=255, default='manually curated, not government-verified')
    address = models.TextField(blank=True, default='')
    contact = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Consultancies"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (Curated)"


class University(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    country = models.CharField(max_length=100, db_index=True)
    source = models.CharField(max_length=100, default='Hipolabs/Wikipedia')
    recognized = models.BooleanField(default=True)
    website = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Universities"
        ordering = ['country', 'name']

    def __str__(self):
        return f"{self.name} ({self.country})"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20, blank=True, default='')
    country = models.CharField(max_length=100, default='Nepal')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class ScamReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reported_entity_name = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=50) # Agency, Consultancy, University, Offer Letter
    user_phone = models.CharField(max_length=50, blank=True, default='')
    user_email = models.CharField(max_length=255, blank=True, default='')
    reason = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    email_sent = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Scam Report #{self.id} for {self.reported_entity_name}"


class VerificationRecord(models.Model):
    VERDICT_CHOICES = (
        ('SAFE', 'Safe 🟢'),
        ('SUSPICIOUS', 'Suspicious 🟡'),
        ('HIGH_RISK', 'High Risk 🔴'),
        ('UNKNOWN', 'Unknown ⚪'),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    verification_type = models.CharField(max_length=50) # AGENCY, CONSULTANCY, UNIVERSITY, OFFER_LETTER
    input_name = models.CharField(max_length=255)
    country = models.CharField(max_length=100, blank=True, default='')
    matched_entity_name = models.CharField(max_length=255, blank=True, default='')
    matched_entity_type = models.CharField(max_length=50, blank=True, default='')
    license_status = models.CharField(max_length=100, blank=True, default='')
    match_score = models.FloatField(default=0.0)
    verdict = models.CharField(max_length=50, choices=VERDICT_CHOICES, default='UNKNOWN')
    verdict_display = models.CharField(max_length=255, blank=True, default='')
    suspicious_phrases = models.JSONField(default=list, blank=True)
    reasons = models.JSONField(default=list, blank=True)
    source_info = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    # NOTE: raw_text containing full PII is explicitly omitted for user privacy safety.

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Record {self.uuid} - {self.input_name} ({self.verdict})"
