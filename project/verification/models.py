from django.db import models

class DataSource(models.TextChoices):
    DOFE = 'dofe', 'DoFE Government Registry'
    MANUAL = 'manual', 'Manually Curated Registry'
    HIPOLABS = 'hipolabs', 'Hipolabs Global Registry'


class Agency(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )

    name = models.CharField(max_length=255, db_index=True)
    permission_no = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='active')
    address = models.TextField(blank=True, default='')
    last_synced = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Agencies"
        ordering = ['name']

    def __init__(self, *args, **kwargs):
        # Backward compatibility for model initialization
        license_number = kwargs.pop('license_number', None)
        if license_number is not None:
            kwargs['permission_no'] = license_number
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if self.status:
            self.status = self.status.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.permission_no}) - {self.get_status_display()}"

    @property
    def license_number(self):
        return self.permission_no

    @license_number.setter
    def license_number(self, value):
        self.permission_no = value

    @property
    def contact(self):
        return ""


class Consultancy(models.Model):
    TYPE_CHOICES = (
        ('business', 'Business Consultancy'),
        ('education', 'Education Consultancy'),
    )

    name = models.CharField(max_length=255, db_index=True)
    consultancy_type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='education', db_index=True)
    address = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='')
    added_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Consultancies"
        ordering = ['name']

    def __init__(self, *args, **kwargs):
        # Pop obsolete fields during initialization
        kwargs.pop('status', None)
        kwargs.pop('source_note', None)
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_consultancy_type_display()})"

    @property
    def status(self):
        return "MANUALLY_CURATED"

    @status.setter
    def status(self, value):
        pass

    @property
    def source_note(self):
        return f"manually curated, not government-verified ({self.get_consultancy_type_display()})"

    @source_note.setter
    def source_note(self, value):
        pass

    @property
    def contact(self):
        return ""


class University(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    country = models.CharField(max_length=100, db_index=True)
    domain = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        verbose_name_plural = "Universities"
        ordering = ['country', 'name']

    def __init__(self, *args, **kwargs):
        # Pop obsolete fields during initialization
        kwargs.pop('recognized', None)
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.country})"

    @property
    def source(self):
        return "Hipolabs/Wikipedia"

    @property
    def recognized(self):
        return True

    @recognized.setter
    def recognized(self, value):
        pass

    @property
    def website(self):
        return f"https://{self.domain}" if self.domain else ""
