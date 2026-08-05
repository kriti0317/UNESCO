from django.test import TestCase
from verification.models import Agency, Consultancy, University
from main.models import VerificationRecord, ScamReport
from main.fuzzy_matcher import match_entity
from main.rule_engine import evaluate_verdict

class ScamVerifierUnitTests(TestCase):

    def setUp(self):
        # Create test records
        self.active_agency = Agency.objects.create(
            name="Prestige Overseas Pvt. Ltd.",
            license_number="1050/074/075",
            status="ACTIVE"
        )
        self.expired_agency = Agency.objects.create(
            name="Royal Gulf Recruitment",
            license_number="305/058/059",
            status="EXPIRED"
        )
        self.consultancy = Consultancy.objects.create(
            name="Alfa Beta Institute",
            status="MANUALLY_CURATED",
            source_note="manually curated, not government-verified"
        )
        self.university = University.objects.create(
            name="University of Sydney",
            country="Australia",
            recognized=True
        )

    def test_fuzzy_matching_engine_85_percent_threshold(self):
        """Test reusable rapidfuzz matcher with slight typos."""
        # 1. Exact & typo match above 85%
        match, score, is_match = match_entity("Prestige Overseas", Agency.objects.all(), threshold=85.0)
        self.assertTrue(is_match)
        self.assertEqual(match.id, self.active_agency.id)
        self.assertGreaterEqual(score, 85.0)

        # 2. Match below threshold
        match_low, score_low, is_match_low = match_entity("Random Fake Bureau", Agency.objects.all(), threshold=85.0)
        self.assertFalse(is_match_low)
        self.assertIsNone(match_low)

    def test_hard_rule_not_found_always_forces_red(self):
        """ASSERT: 'Not found' in DB always forces RED (High Risk)."""
        verdict = evaluate_verdict(
            entity_name="NonExistent Fraud Agency",
            matched_entity=None,
            is_matched=False,
            entity_type="AGENCY",
            suspicious_phrases=[]
        )
        self.assertEqual(verdict['verdict'], 'HIGH_RISK')
        self.assertEqual(verdict['badge_color'], 'red')
        self.assertIn('High Risk', verdict['verdict_title'])

    def test_consultancy_verdict_capped_at_suspicious(self):
        """ASSERT: Consultancies can NEVER be 🟢 Safe (must be capped at Suspicious / Found Curated)."""
        verdict = evaluate_verdict(
            entity_name="Alfa Beta Institute",
            matched_entity=self.consultancy,
            is_matched=True,
            entity_type="CONSULTANCY",
            suspicious_phrases=[]
        )
        self.assertNotEqual(verdict['verdict'], 'SAFE')
        self.assertEqual(verdict['verdict'], 'SUSPICIOUS')
        self.assertEqual(verdict['badge_color'], 'yellow')
        self.assertTrue(verdict['is_curated_disclaimer'])
        self.assertIn('Manually curated', verdict['reasons'][1])


    def test_active_agency_verdict(self):
        """Active agency with no suspicious phrases must be 🟢 Safe."""
        verdict = evaluate_verdict(
            entity_name="Prestige Overseas Pvt. Ltd.",
            matched_entity=self.active_agency,
            is_matched=True,
            entity_type="AGENCY",
            suspicious_phrases=[]
        )
        self.assertEqual(verdict['verdict'], 'SAFE')
        self.assertEqual(verdict['badge_color'], 'green')

    def test_active_agency_with_suspicious_phrases(self):
        """Active agency with 1+ suspicious phrases must be 🟡 Suspicious."""
        verdict = evaluate_verdict(
            entity_name="Prestige Overseas Pvt. Ltd.",
            matched_entity=self.active_agency,
            is_matched=True,
            entity_type="AGENCY",
            suspicious_phrases=["Requests advance payment via eSewa"]
        )
        self.assertEqual(verdict['verdict'], 'SUSPICIOUS')
        self.assertEqual(verdict['badge_color'], 'yellow')

    def test_expired_agency_verdict(self):
        """Expired agency must force 🔴 High Risk."""
        verdict = evaluate_verdict(
            entity_name="Royal Gulf Recruitment",
            matched_entity=self.expired_agency,
            is_matched=True,
            entity_type="AGENCY",
            suspicious_phrases=[]
        )
        self.assertEqual(verdict['verdict'], 'HIGH_RISK')
        self.assertEqual(verdict['badge_color'], 'red')

    def test_pii_omitted_from_verification_record(self):
        """Verify that VerificationRecord does not store full PII raw_text."""
        record = VerificationRecord.objects.create(
            input_name="Test Agency",
            verdict="SAFE"
        )
        self.assertFalse(hasattr(record, 'raw_text'))
