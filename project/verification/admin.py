from django.contrib import admin
from .models import Agency, Consultancy, University

@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'permission_no', 'status', 'last_synced')
    search_fields = ('name', 'permission_no', 'address')
    list_filter = ('status',)


@admin.register(Consultancy)
class ConsultancyAdmin(admin.ModelAdmin):
    list_display = ('name', 'consultancy_type', 'address', 'added_on')
    search_fields = ('name', 'address', 'notes')
    list_filter = ('consultancy_type',)


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'domain')
    search_fields = ('name', 'country', 'domain')
    list_filter = ('country',)
