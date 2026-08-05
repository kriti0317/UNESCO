import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from verification.models import Agency, Consultancy, University

class Command(BaseCommand):
    help = 'Seeds initial Agency, Consultancy, and University database records'

    def handle(self, *args, **options):
        self.stdout.write("Starting database seeding...")

        # 1. Seed Agencies (DoFE Manpower Agencies in Nepal)
        self.stdout.write("Seeding Agencies...")
        agency_data = [
            # Active Agencies
            ("Prestige International Overseas Pvt. Ltd.", "1050/074/075", "ACTIVE", "Gongabu, Kathmandu", "+977-1-4388888"),
            ("Al-Hira Overseas Pvt. Ltd.", "892/067/068", "ACTIVE", "Battisputali, Kathmandu", "+977-1-4471234"),
            ("Apex Manpower Recruitment Pvt. Ltd.", "642/063/064", "ACTIVE", "Gaushala, Kathmandu", "+977-1-4489999"),
            ("SOS Manpower Service Pvt. Ltd.", "124/058/059", "ACTIVE", "Dhumbarahi, Kathmandu", "+977-1-4433221"),
            ("Karnali Overseas Pvt. Ltd.", "741/064/065", "ACTIVE", "Sinamangal, Kathmandu", "+977-1-4110022"),
            ("Gulf Employment Manpower Agency", "532/062/063", "ACTIVE", "Naya Baneshwor, Kathmandu", "+977-1-4491100"),
            ("Imperial Overseas Pvt. Ltd.", "990/072/073", "ACTIVE", "Chabahil, Kathmandu", "+977-1-4475566"),
            ("Nile Overseas Recruitment Services", "410/060/061", "ACTIVE", "Lalitpur, Nepal", "+977-1-5544332"),
            ("Universal Manpower Consultancy", "1102/075/076", "ACTIVE", "Kathmandu", "+977-1-4781200"),
            ("Alliance Overseas Pvt. Ltd.", "331/059/060", "ACTIVE", "Gongabu, Kathmandu", "+977-1-4356789"),
            ("Skyway Management Pvt. Ltd.", "812/066/067", "ACTIVE", "Samakhusi, Kathmandu", "+977-1-4380011"),
            ("Dynamic Staffing Solutions Pvt. Ltd.", "1015/073/074", "ACTIVE", "Koteshwor, Kathmandu", "+977-1-4601122"),
            ("Himalayan Human Resources Pvt. Ltd.", "650/063/064", "ACTIVE", "Baneshwor, Kathmandu", "+977-1-4487788"),
            ("Shikhar International Manpower Services", "778/065/066", "ACTIVE", "Mitrapark, Kathmandu", "+977-1-4465432"),
            ("Prabhu Overseas Pvt. Ltd.", "920/069/070", "ACTIVE", "Chabahil, Kathmandu", "+977-1-4498765"),

            # Expired Licenses
            ("Royal Gulf Manpower Service", "305/058/059", "EXPIRED", "Sundhara, Kathmandu", "+977-1-4221100"),
            ("FastTrack Overseas Placement", "612/062/063", "EXPIRED", "Kalanki, Kathmandu", "+977-1-4275544"),
            ("Global Star Recruitment Center", "840/066/067", "EXPIRED", "Balkhu, Kathmandu", "+977-1-4289900"),
            ("Pacific Human Resource Pvt. Ltd.", "450/060/061", "EXPIRED", "Lalitpur", "+977-1-5523344"),
            ("Everest Placement Agency", "210/056/057", "EXPIRED", "Kathmandu", "+977-1-4412233"),

            # Cancelled / Suspended Licenses
            ("FakeTrust Manpower Overseas Pvt. Ltd.", "999/099/099", "CANCELLED", "Chabahil, Kathmandu", "+977-1-9999999"),
            ("Blacklisted Gulf Recruiter Agency", "101/055/056", "CANCELLED", "Gongabu, Kathmandu", "+977-1-4389999"),
            ("Fraudster International Recruitment", "777/065/066", "CANCELLED", "Sinamangal, Kathmandu", "+977-1-4119988"),
            ("Shadow Foreign Job Bureau", "888/067/068", "CANCELLED", "Koteshwor, Kathmandu", "+977-1-4600000"),
        ]

        created_agencies = 0
        for name, lic, status, addr, contact in agency_data:
            _, created = Agency.objects.get_or_create(
                name=name,
                defaults={
                    'license_number': lic,
                    'status': status,
                    'address': addr,
                    'contact': contact,
                    'source_url': 'https://foreignjob.dofe.gov.np',
                }
            )
            if created:
                created_agencies += 1

        self.stdout.write(f"Created {created_agencies} Agencies.")

        # 2. Seed Consultancies (Curated Nepal Education Consultancies)
        self.stdout.write("Seeding Consultancies...")
        consultancy_names = [
            ("Alfa Beta Institute", "New Baneshwor, Kathmandu", "+977-1-4780123"),
            ("Kangaroo Education Foundation", "Putalisadak, Kathmandu", "+977-1-4242000"),
            ("Edwise Foundation", "New Baneshwor, Kathmandu", "+977-1-4428900"),
            ("NIEC (Nepal International Educational Consultancy)", "Putalisadak, Kathmandu", "+977-1-4256600"),
            ("Grace International Educational Consultancy", "Minbhawan, Kathmandu", "+977-1-4107100"),
            ("Expert Education and Visa Services", "Maharajgunj, Kathmandu", "+977-1-4720000"),
            ("IDP Education Nepal", "Hattisar, Kathmandu", "+977-1-4426677"),
            ("AECC Global Nepal", "Kamalpokhari, Kathmandu", "+977-1-4420011"),
            ("Orbit International Education", "Putalisadak, Kathmandu", "+977-1-4261100"),
            ("Global Reach Nepal", "Dillibazar, Kathmandu", "+977-1-4443322"),
            ("Study International Consultancy", "Lalitpur", "+977-1-5534455"),
            ("Bridge International Educational Consultancy", "Kumaripati, Lalitpur", "+977-1-5521100"),
            ("Broadways Education Pvt. Ltd.", "Bagbazar, Kathmandu", "+977-1-4240011"),
            ("Edu-Consult Nepal", "Pokhara, Nepal", "+977-61-523344"),
            ("Apex Educational Academy", "Chitwan, Nepal", "+977-56-521100"),
            ("Landmark Education Consultancy", "Putalisadak, Kathmandu", "+977-1-4245566"),
            ("Options Educational Consultancy", "New Baneshwor, Kathmandu", "+977-1-4789900"),
            ("Rights Education Foundation", "Lalitpur", "+977-1-5544110"),
            ("Silicon Education Network", "Putalisadak, Kathmandu", "+977-1-4260022"),
            ("Valley International Education", "Bhairahawa, Nepal", "+977-71-520100"),
        ]

        created_consultancies = 0
        for name, addr, contact in consultancy_names:
            _, created = Consultancy.objects.get_or_create(
                name=name,
                defaults={
                    'status': 'MANUALLY_CURATED',
                    'source_note': 'manually curated, not government-verified',
                    'address': addr,
                    'contact': contact,
                }
            )
            if created:
                created_consultancies += 1

        self.stdout.write(f"Created {created_consultancies} Consultancies.")

        # 3. Seed Universities (Nepal + Popular Destinations + Hipolabs API)
        self.stdout.write("Seeding Universities...")
        university_data = [
            # Nepal
            ("Tribhuvan University", "Nepal", "https://tu.edu.np"),
            ("Kathmandu University", "Nepal", "https://ku.edu.np"),
            ("Pokhara University", "Nepal", "https://pu.edu.np"),
            ("Purbanchal University", "Nepal", "https://purbanchaluniv.edu.np"),
            ("Lumbini Buddhist University", "Nepal", "https://lbu.edu.np"),
            ("Mid-Western University", "Nepal", "https://mwu.edu.np"),
            ("Far-Western University", "Nepal", "https://fwu.edu.np"),

            # USA
            ("Harvard University", "United States", "https://harvard.edu"),
            ("Massachusetts Institute of Technology (MIT)", "United States", "https://mit.edu"),
            ("Stanford University", "United States", "https://stanford.edu"),
            ("Columbia University", "United States", "https://columbia.edu"),
            ("University of California, Berkeley", "United States", "https://berkeley.edu"),
            ("New York University (NYU)", "United States", "https://nyu.edu"),
            ("University of Texas at Arlington", "United States", "https://uta.edu"),

            # Australia
            ("The University of Sydney", "Australia", "https://sydney.edu.au"),
            ("The University of Melbourne", "Australia", "https://unimelb.edu.au"),
            ("Monash University", "Australia", "https://monash.edu"),
            ("The University of Queensland", "Australia", "https://uq.edu.au"),
            ("UNSW Sydney (University of New South Wales)", "Australia", "https://unsw.edu.au"),
            ("Macquarie University", "Australia", "https://mq.edu.au"),

            # UK
            ("University of Oxford", "United Kingdom", "https://ox.ac.uk"),
            ("University of Cambridge", "United Kingdom", "https://cam.ac.uk"),
            ("Imperial College London", "United Kingdom", "https://imperial.ac.uk"),
            ("University College London (UCL)", "United Kingdom", "https://ucl.ac.uk"),
            ("The University of Edinburgh", "United Kingdom", "https://ed.ac.uk"),

            # Canada
            ("University of Toronto", "Canada", "https://utoronto.ca"),
            ("University of British Columbia", "Canada", "https://ubc.ca"),
            ("McGill University", "Canada", "https://mcgill.ca"),
            ("University of Waterloo", "Canada", "https://uwaterloo.ca"),

            # Japan & Korea & India
            ("The University of Tokyo", "Japan", "https://u-tokyo.ac.jp"),
            ("Kyoto University", "Japan", "https://kyoto-u.ac.jp"),
            ("Seoul National University", "Korea, Republic of", "https://snu.ac.kr"),
            ("Jawaharlal Nehru University", "India", "https://jnu.ac.in"),
            ("Indian Institute of Technology Delhi (IITD)", "India", "https://iitd.ac.in"),
        ]

        created_unis = 0
        for name, country, web in university_data:
            _, created = University.objects.get_or_create(
                name=name,
                country=country,
                defaults={
                    'source': 'Hipolabs/Wikipedia',
                    'recognized': True,
                    'website': web
                }
            )
            if created:
                created_unis += 1

        # Attempt to pull additional live records from Hipolabs API if available
        try:
            res = requests.get("http://universities.hipolabs.com/search?country=Australia", timeout=4)
            if res.status_code == 200:
                h_data = res.json()
                for item in h_data[:15]:
                    u_name = item.get('name')
                    domains = item.get('web_pages', [])
                    web = domains[0] if domains else None
                    if u_name:
                        _, c = University.objects.get_or_create(
                            name=u_name,
                            country='Australia',
                            defaults={'source': 'Hipolabs API', 'recognized': True, 'website': web}
                        )
                        if c: created_unis += 1
        except Exception as e:
            self.stdout.write(f"Hipolabs API fetch optional note: {e}")

        self.stdout.write(f"Created {created_unis} Universities.")
        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
