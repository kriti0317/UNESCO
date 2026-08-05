from django.test import TestCase
from verification.models import Agency, Consultancy, University
from main.models import VerificationRecord, ScamReport
from main.fuzzy_matcher import match_entity
from main.rule_engine import evaluate_verdict
from verification.pipelines import run_scholarship_letter_pipeline

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
        self.university_toronto = University.objects.create(
            name="University of Toronto",
            country="Canada",
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

    def test_scholarship_pipeline_flags_common_fake_letter_patterns(self):
        """Fake scholarship letters should be flagged for upfront fees, admission guarantees, and unrealistic scholarship promises."""
        pipeline_result = run_scholarship_letter_pipeline(
            "University: University of Sydney\n"
            "Scholarship Offer: 100% full tuition waiver + guaranteed housing\n"
            "Deposit $500 processing fee to personal eSewa account\n"
            "Guaranteed admission to the program without interview\n"
            "Processed by Global Education Services"
        )

        self.assertIn('Upfront processing, security deposit, or administrative fees requested in scholarship offer.', pipeline_result['ai_detected_flags'])
        self.assertIn('Letter contains guaranteed admission, enrollment, or entry language.', pipeline_result['ai_detected_flags'])
        self.assertIn('Contains unrealistic benefit promises (e.g. 100% scholarship without standard application evaluation).', pipeline_result['ai_detected_flags'])
        self.assertTrue(pipeline_result['evidence'])
        self.assertIn('Suspicious', pipeline_result['final_verdict'])

    def test_small_scholarship_amount_and_degree_level_should_not_be_suspicious_by_default(self):
        """A normal scholarship amount for Master or Bachelor study should not be auto-flagged just because a small amount or degree level appears in the letter."""
        pipeline_result = run_scholarship_letter_pipeline(
            "University: University of Sydney\n"
            "Scholarship amount: USD 2000 for Master's degree\n"
            "No upfront fee required\n"
            "Admission is subject to normal document review"
        )

        self.assertEqual([], pipeline_result['ai_detected_flags'])
        self.assertIn('Safe', pipeline_result['final_verdict'])

    def test_small_scholarship_amount_with_no_fee_demand_must_not_raise_flag(self):
        """A modest scholarship amount should not be treated as suspicious merely because it references fee or degree-level language."""
        pipeline_result = run_scholarship_letter_pipeline(
            "University: University of Toronto\n"
            "Scholarship amount: USD 750 for Bachelor's degree\n"
            "Standard tuition fee is stated in the official offer\n"
            "No upfront payment is required"
        )

        self.assertEqual([], pipeline_result['ai_detected_flags'])
        self.assertIn('Safe', pipeline_result['final_verdict'])

    def test_pii_omitted_from_verification_record(self):
        """Verify that VerificationRecord does not store full PII raw_text."""
        record = VerificationRecord.objects.create(
            input_name="Test Agency",
            verdict="SAFE"
        )
        self.assertFalse(hasattr(record, 'raw_text'))

    def test_verification_fuzzy_find_wratio(self):
        """Test verification fuzzy_find with WRatio matching partial names."""
        from verification.fuzzy_matcher import fuzzy_find
        match, score = fuzzy_find("Prestige Overseas", Agency.objects.all(), field="name")
        self.assertIsNotNone(match)
        self.assertEqual(match.id, self.active_agency.id)

    def test_sync_csv_data_command(self):
        """Test sync_csv_data management command execution."""
        from django.core.management import call_command
        call_command('sync_csv_data')
        self.assertGreater(Agency.objects.count(), 2)
        self.assertGreater(Consultancy.objects.count(), 1)
        self.assertGreater(University.objects.count(), 1)

    def test_chatbot_rag_entity_retrieval(self):
        """Test chatbot RAG query retrieves correct entity despite conversational stopwords."""
        from main.chatbot import query_rag_chatbot
        reply = query_rag_chatbot("Can you please check about Prestige Overseas?")
        self.assertIn("Prestige Overseas", reply)

