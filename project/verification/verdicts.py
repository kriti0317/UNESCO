from dataclasses import dataclass
from enum import Enum
from verification.models import Agency, Consultancy, University, DataSource
from verification.fuzzy_matcher import fuzzy_find

class RiskLevel(str, Enum):
    SAFE = 'SAFE'
    SUSPICIOUS = 'SUSPICIOUS'
    HIGH_RISK = 'HIGH_RISK'
    UNKNOWN = 'UNKNOWN'


@dataclass
class Verdict:
    risk_level: RiskLevel
    label: str
    source: DataSource
    is_verified_source: bool
    reasons: list[str]
    matched_record: dict | None


def agency_to_dict(agency) -> dict:
    return {
        'id': agency.id,
        'name': agency.name,
        'permission_no': agency.permission_no,
        'license_number': agency.permission_no,  # backward compatibility
        'status': agency.status,
        'address': agency.address,
        'last_synced': agency.last_synced.isoformat() if agency.last_synced else None
    }


def consultancy_to_dict(consultancy) -> dict:
    return {
        'id': consultancy.id,
        'name': consultancy.name,
        'consultancy_type': consultancy.consultancy_type,
        'address': consultancy.address,
        'notes': consultancy.notes,
        'added_on': consultancy.added_on.isoformat() if consultancy.added_on else None,
        'status': "MANUALLY_CURATED",
        'source_note': f"manually curated, not government-verified ({consultancy.get_consultancy_type_display()})"
    }


def university_to_dict(university) -> dict:
    return {
        'id': university.id,
        'name': university.name,
        'country': university.country,
        'domain': university.domain,
        'source': "Hipolabs/Wikipedia",
        'recognized': True,
        'website': f"https://{university.domain}" if university.domain else ""
    }


def verify_agency(name: str) -> Verdict:
    """
    Fuzzy matches agency name against DoFE active/expired/cancelled agencies.
    Returns a deterministic Verdict.
    """
    agencies = Agency.objects.all()
    match, score = fuzzy_find(name, agencies, field="name")

    if match:
        serialized = agency_to_dict(match)
        status_lower = match.status.lower()
        if status_lower == 'active':
            return Verdict(
                risk_level=RiskLevel.SAFE,
                label="✅ Licensed",
                source=DataSource.DOFE,
                is_verified_source=True,
                reasons=["Agency is registered and currently Active in the Department of Foreign Employment (DoFE) registry."],
                matched_record=serialized
            )
        elif status_lower == 'expired':
            return Verdict(
                risk_level=RiskLevel.HIGH_RISK,
                label="❌ License Expired",
                source=DataSource.DOFE,
                is_verified_source=True,
                reasons=["Agency license has EXPIRED. Operating under an expired license is illegal and unsafe."],
                matched_record=serialized
            )
        else:  # cancelled or suspended
            return Verdict(
                risk_level=RiskLevel.HIGH_RISK,
                label="❌ License Cancelled",
                source=DataSource.DOFE,
                is_verified_source=True,
                reasons=["Agency license has been CANCELLED or suspended. Recruiting workers under a cancelled license is illegal."],
                matched_record=serialized
            )
    else:
        return Verdict(
            risk_level=RiskLevel.HIGH_RISK,
            label="❌ Not Listed",
            source=DataSource.DOFE,
            is_verified_source=False,
            reasons=["Agency was not found in the official DoFE database."],
            matched_record=None
        )


def verify_consultancy(name: str, consultancy_type: str) -> Verdict:
    """
    Fuzzy matches consultancy name against manually curated database.
    """
    consultancies = Consultancy.objects.filter(consultancy_type=consultancy_type)
    match, score = fuzzy_find(name, consultancies, field="name")
    
    # reasons must explicitly state "no public government registry exists for {business/education} consultancies"
    registry_disclaimer = f"no public government registry exists for {consultancy_type} consultancies"

    if match:
        serialized = consultancy_to_dict(match)
        return Verdict(
            risk_level=RiskLevel.UNKNOWN,
            label="⚠️ Curated Record",
            source=DataSource.MANUAL,
            is_verified_source=False,
            reasons=[
                registry_disclaimer,
                "Consultancy name is listed in our manually curated registry."
            ],
            matched_record=serialized
        )
    else:
        return Verdict(
            risk_level=RiskLevel.UNKNOWN,
            label="❌ Not Listed",
            source=DataSource.MANUAL,
            is_verified_source=False,
            reasons=[
                registry_disclaimer,
                "Consultancy was not found in our manually curated database."
            ],
            matched_record=None
        )


def verify_university(name: str) -> Verdict:
    """
    Fuzzy matches university name against recognized global universities.
    """
    unis = University.objects.all()
    match, score = fuzzy_find(name, unis, field="name")

    if match:
        serialized = university_to_dict(match)
        return Verdict(
            risk_level=RiskLevel.SAFE,
            label="🟢 Recognized",
            source=DataSource.HIPOLABS,
            is_verified_source=False,
            reasons=["University is recognized in public global database registries."],
            matched_record=serialized
        )
    else:
        return Verdict(
            risk_level=RiskLevel.HIGH_RISK,
            label="❌ Not Listed",
            source=DataSource.HIPOLABS,
            is_verified_source=False,
            reasons=["University was not found in our recognized foreign universities database."],
            matched_record=None
        )


def get_risk_verdict(entity_verdict: Verdict, red_flags: list[str]) -> str:
    """
    Returns the final verdict string using a deterministic decision table:
    1. If label == "❌ Not Listed" -> "🔴 High Risk"
    2. If label indicates expired/cancelled/suspended -> "🔴 High Risk"
    3. If risk_level == RiskLevel.UNKNOWN -> "⚠️ Unknown — Verify Manually"
    4. If licensed+active (SAFE) and red_flags is non-empty -> "🟡 Suspicious"
    5. If licensed+active (SAFE) and red_flags is empty -> "🟢 Safe"
    """
    # 1. Not Listed check
    if entity_verdict.label == "❌ Not Listed":
        return "🔴 High Risk"
        
    # 2. Expired / cancelled / suspended check
    label_lower = entity_verdict.label.lower()
    if "expired" in label_lower or "cancelled" in label_lower or "suspended" in label_lower:
        return "🔴 High Risk"
        
    # 3. Unknown check
    if entity_verdict.risk_level == RiskLevel.UNKNOWN:
        return "⚠️ Unknown — Verify Manually"
        
    # 4. Safe check (licensed + active)
    if entity_verdict.risk_level == RiskLevel.SAFE:
        if red_flags:
            return "🟡 Suspicious"
        else:
            return "🟢 Safe"
            
    # Default fallback
    return "⚠️ Unknown — Verify Manually"
