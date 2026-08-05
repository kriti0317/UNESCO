import os
import csv
import re
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from verification.models import Agency, Consultancy, University


class Command(BaseCommand):
    help = 'Syncs database records from docs/ CSV datasets (Agencies, Consultancies, Universities)'

    def handle(self, *args, **options):
        self.stdout.write("Starting CSV data ingestion...")

        # Base directory for docs (UNESCO/project/docs or project root docs)
        base_dir = Path(settings.BASE_DIR)
        docs_dir = base_dir / 'docs'
        if not docs_dir.exists():
            docs_dir = base_dir.parent / 'docs'

        if not docs_dir.exists():
            self.stderr.write(self.style.ERROR(f"Docs directory not found at {docs_dir}"))
            return

        # 1. Sync Recruitment Agencies
        agencies_csv = docs_dir / 'recruitment_agencies.csv'
        if agencies_csv.exists():
            self.stdout.write("Ingesting recruitment_agencies.csv...")
            self.sync_agencies(agencies_csv)
        else:
            self.stdout.write(self.style.WARNING("recruitment_agencies.csv not found."))

        # 2. Sync Education Consultancies
        edu_csv = docs_dir / 'education_consultancies.csv'
        if edu_csv.exists():
            self.stdout.write("Ingesting education_consultancies.csv...")
            self.sync_consultancies(edu_csv, consultancy_type='education')
        else:
            self.stdout.write(self.style.WARNING("education_consultancies.csv not found."))

        # 3. Sync Business Consultancies
        biz_csv = docs_dir / 'business_consultancies.csv'
        if biz_csv.exists():
            self.stdout.write("Ingesting business_consultancies.csv...")
            self.sync_consultancies(biz_csv, consultancy_type='business')
        else:
            self.stdout.write(self.style.WARNING("business_consultancies.csv not found."))

        # 4. Sync Universities
        uni_csv = docs_dir / 'universities.csv'
        if uni_csv.exists():
            self.stdout.write("Ingesting universities.csv...")
            self.sync_universities(uni_csv)
        else:
            self.stdout.write(self.style.WARNING("universities.csv not found."))

        self.stdout.write(self.style.SUCCESS("CSV Data Ingestion complete!"))

    def sync_agencies(self, csv_path):
        count = 0
        with open(csv_path, mode='r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader, start=1):
                name = (row.get('Name') or '').strip()
                if not name or name.startswith('—') or name.startswith('--'):
                    continue

                notes = (row.get('Category / Notes') or '').strip()
                reg_status = (row.get('Registration / Corporate Status') or '').strip()
                op_status = (row.get('Operating Status') or '').strip()
                country = (row.get('Country') or '').strip()
                website = (row.get('Domain / Website') or '').strip()

                full_text = f"{notes} {reg_status} {op_status}".lower()

                # Determine status
                if 'expired' in full_text:
                    status = 'expired'
                elif any(k in full_text for k in ['cancelled', 'suspended', 'blacklisted', 'fraud']):
                    status = 'cancelled'
                else:
                    status = 'active'

                # Extract or generate permission_no
                perm_match = re.search(r'(?:license\s*(?:no\.?)?|dofe[^\d]*)\s*([0-9/\-\.A-Za-z]+)', f"{reg_status} {notes}", re.IGNORECASE)
                if perm_match:
                    perm_no = perm_match.group(1).strip()
                else:
                    clean_slug = re.sub(r'[^a-zA-Z0-9]', '', name)[:12].upper()
                    perm_no = f"REG-{clean_slug}-{row_idx:03d}"

                address = f"{country}".strip()
                if website and website != 'Not verified':
                    address = f"{address} ({website})".strip()

                Agency.objects.update_or_create(
                    permission_no=perm_no,
                    defaults={
                        'name': name,
                        'status': status,
                        'address': address
                    }
                )
                count += 1
        self.stdout.write(f" - Processed {count} Agency records.")

    def sync_consultancies(self, csv_path, consultancy_type):
        count = 0
        with open(csv_path, mode='r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get('Name') or '').strip()
                if not name or name.startswith('—') or name.startswith('--'):
                    continue

                country = (row.get('Country') or '').strip()
                website = (row.get('Domain / Website') or '').strip()
                notes = (row.get('Category / Notes') or '').strip()

                addr_parts = [p for p in [country, website if website != 'Not verified' else ''] if p]
                address = ", ".join(addr_parts)

                Consultancy.objects.update_or_create(
                    name=name,
                    consultancy_type=consultancy_type,
                    defaults={
                        'address': address,
                        'notes': notes
                    }
                )
                count += 1
        self.stdout.write(f" - Processed {count} Consultancy ({consultancy_type}) records.")

    def sync_universities(self, csv_path):
        count = 0
        with open(csv_path, mode='r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get('Name') or '').strip()
                if not name or name.startswith('—') or name.startswith('--'):
                    continue

                country = (row.get('Country') or '').strip()
                domain_raw = (row.get('Domain / Website') or '').strip()
                # Clean domain string
                domain = re.sub(r'^https?://', '', domain_raw, flags=re.IGNORECASE)
                domain = re.sub(r'^www\.', '', domain, flags=re.IGNORECASE).rstrip('/')

                University.objects.update_or_create(
                    name=name,
                    country=country,
                    defaults={
                        'domain': domain
                    }
                )
                count += 1
        self.stdout.write(f" - Processed {count} University records.")
