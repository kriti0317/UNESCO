import requests
from django.core.management.base import BaseCommand
from verification.models import University

class Command(BaseCommand):
    help = 'Syncs universities from the Hipolabs API with local fallback'

    def handle(self, *args, **options):
        self.stdout.write("Starting foreign university registry sync...")

        countries = ["Nepal", "Australia", "United Kingdom", "United States", "Canada"]
        upserted_count = 0

        # Pre-defined fallback database for offline/sandboxed execution
        fallback_unis = [
            # Nepal
            ("Tribhuvan University", "Nepal", "tu.edu.np"),
            ("Kathmandu University", "Nepal", "ku.edu.np"),
            ("Pokhara University", "Nepal", "pu.edu.np"),
            ("Purbanchal University", "Nepal", "purbanchaluniv.edu.np"),
            ("Lumbini Buddhist University", "Nepal", "lbu.edu.np"),
            ("Mid-Western University", "Nepal", "mwu.edu.np"),
            ("Far-Western University", "Nepal", "fwu.edu.np"),

            # USA
            ("Harvard University", "United States", "harvard.edu"),
            ("Massachusetts Institute of Technology (MIT)", "United States", "mit.edu"),
            ("Stanford University", "United States", "stanford.edu"),
            ("Columbia University", "United States", "columbia.edu"),
            ("University of California, Berkeley", "United States", "berkeley.edu"),
            ("New York University (NYU)", "United States", "nyu.edu"),
            ("University of Texas at Arlington", "United States", "uta.edu"),

            # Australia
            ("The University of Sydney", "Australia", "sydney.edu.au"),
            ("The University of Melbourne", "Australia", "unimelb.edu.au"),
            ("Monash University", "Australia", "monash.edu"),
            ("The University of Queensland", "Australia", "uq.edu.au"),
            ("UNSW Sydney (University of New South Wales)", "Australia", "unsw.edu.au"),
            ("Macquarie University", "Australia", "mq.edu.au"),

            # UK
            ("University of Oxford", "United Kingdom", "ox.ac.uk"),
            ("University of Cambridge", "United Kingdom", "cam.ac.uk"),
            ("Imperial College London", "United Kingdom", "imperial.ac.uk"),
            ("University College London (UCL)", "United Kingdom", "ucl.ac.uk"),
            ("The University of Edinburgh", "United Kingdom", "ed.ac.uk"),

            # Canada
            ("University of Toronto", "Canada", "utoronto.ca"),
            ("University of British Columbia", "Canada", "ubc.ca"),
            ("McGill University", "Canada", "mcgill.ca"),
            ("University of Waterloo", "Canada", "uwaterloo.ca"),
        ]

        synced_via_api = False

        for country in countries:
            self.stdout.write(f"Syncing universities for {country} via Hipolabs API...")
            try:
                # 4-second timeout to prevent command hangs
                url = f"http://universities.hipolabs.com/search?country={country}"
                res = requests.get(url, timeout=4)
                if res.status_code == 200:
                    data = res.json()
                    self.stdout.write(f" - Found {len(data)} universities for {country}.")
                    
                    # Take the first 30 from each country to prevent database bloat during hackathon
                    for item in data[:30]:
                        name = item.get('name')
                        domains = item.get('domains', [])
                        domain = domains[0] if domains else ""
                        if name:
                            _, created = University.objects.update_or_create(
                                name=name,
                                country=country,
                                defaults={'domain': domain}
                            )
                            upserted_count += 1
                    synced_via_api = True
                else:
                    self.stdout.write(self.style.WARNING(f" - API returned status: {res.status_code} for {country}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f" - API request failed for {country}: {e}"))

        if not synced_via_api:
            self.stdout.write(self.style.NOTICE("API Sync was unavailable. Seeding from local fallback university list..."))
            for name, country, domain in fallback_unis:
                _, created = University.objects.update_or_create(
                    name=name,
                    country=country,
                    defaults={'domain': domain}
                )
                upserted_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully sync'd {upserted_count} university records."))
