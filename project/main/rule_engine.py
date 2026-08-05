"""
Deterministic Fixed Rule Engine for Scam Verifier.

HARD RULE GUARANTEE:
AI (LLM/OCR) is ONLY allowed to extract text/entities from documents.
AI must NEVER produce the final verdict ("Safe", "Suspicious", "High Risk", "Unknown").
All verdicts come strictly from this fixed, deterministic decision engine.

GOLDEN RULE:
# HARD RULE: "Not found" in DB always forces RED (High Risk), regardless of how clean the letter text looks.
"""

def evaluate_verdict(entity_name, matched_entity, is_matched, entity_type, suspicious_phrases=None):
    """
    Evaluates the verdict using the strict deterministic matrix.
    
    Parameters:
        entity_name (str): Original input or OCR-extracted name
        matched_entity (Model instance or None): Matched Agency, Consultancy, or University
        is_matched (bool): True if fuzzy match ratio >= 85%
        entity_type (str): 'AGENCY', 'CONSULTANCY', 'UNIVERSITY', or 'OFFER_LETTER'
        suspicious_phrases (list): List of detected suspicious red-flag phrases from document
        
    Returns:
        dict: {
            'verdict': 'SAFE' | 'SUSPICIOUS' | 'HIGH_RISK' | 'UNKNOWN',
            'badge_color': 'green' | 'yellow' | 'red' | 'gray',
            'verdict_title': str,
            'reasons': list of strings,
            'source_info': str,
            'license_status': str,
            'is_curated_disclaimer': bool,
        }
    """
    suspicious_phrases = suspicious_phrases or []
    reasons = []
    
    # Check for empty / unclear name first
    if not entity_name or not entity_name.strip() or entity_name.strip().lower() in ['unknown', 'n/a', 'none', 'unclear']:
        return {
            'verdict': 'UNKNOWN',
            'badge_color': 'gray',
            'verdict_title': '⚪ Unknown — Verify Manually',
            'reasons': ['Organization name could not be clearly extracted or verified.'],
            'source_info': 'Unclear input',
            'license_status': 'N/A',
            'is_curated_disclaimer': False,
        }
        
    # HARD RULE CHECK: "Not found" always forces RED (High Risk)
    if not is_matched or matched_entity is None:
        reasons.append(f"'{entity_name}' was NOT found in our verified government & recognized registries (85% similarity threshold).")
        reasons.append("HARD RULE ENFORCED: Unregistered or unverified entities automatically receive a High Risk alert.")
        if suspicious_phrases:
            reasons.append(f"Detected {len(suspicious_phrases)} suspicious flag(s) in document.")
            
        return {
            'verdict': 'HIGH_RISK',
            'badge_color': 'red',
            'verdict_title': '🔴 High Risk — Unregistered Entity',
            'reasons': reasons,
            'source_info': 'Verified Registry Lookup',
            'license_status': 'Not Licensed',
            'is_curated_disclaimer': False,
        }
        
    # Check entity type of the matched instance
    matched_class_name = matched_entity.__class__.__name__
    
    # 1. Consultancy Match Branch
    if matched_class_name == 'Consultancy' or entity_type == 'CONSULTANCY':
        reasons.append(f"Matched Record: {matched_entity.name}")
        reasons.append("DISCLAIMER: Manually curated record — NOT government-licensed by DoFE.")
        if suspicious_phrases:
            reasons.append(f"Detected {len(suspicious_phrases)} suspicious phrase(s) in document.")
            
        # CAPPED AT SUSPICIOUS / CURATED (Never 🟢 Safe because consultancies lack government licenses)
        return {
            'verdict': 'SUSPICIOUS',
            'badge_color': 'yellow',
            'verdict_title': '🟡 Found — Manually Curated (Not Government-Verified)',
            'reasons': reasons,
            'source_info': matched_entity.source_note,
            'license_status': 'Curated Record',
            'is_curated_disclaimer': True,
        }
        
    # 2. University Match Branch
    if matched_class_name == 'University' or entity_type == 'UNIVERSITY':
        reasons.append(f"Matched Institution: {matched_entity.name} ({matched_entity.country})")
        reasons.append(f"Source: {matched_entity.source}")
        
        if suspicious_phrases:
            reasons.append(f"Warning: Document contains {len(suspicious_phrases)} suspicious phrase(s).")
            return {
                'verdict': 'SUSPICIOUS',
                'badge_color': 'yellow',
                'verdict_title': '🟡 Suspicious — Recognized Institution with Red Flags',
                'reasons': reasons,
                'source_info': matched_entity.source,
                'license_status': 'Recognized Institution',
                'is_curated_disclaimer': False,
            }
        else:
            return {
                'verdict': 'SAFE',
                'badge_color': 'green',
                'verdict_title': '🟢 Recognized Foreign University',
                'reasons': reasons,
                'source_info': matched_entity.source,
                'license_status': 'Recognized Institution',
                'is_curated_disclaimer': False,
            }

    # 3. Agency Match Branch
    if matched_class_name == 'Agency' or entity_type in ['AGENCY', 'OFFER_LETTER']:
        status = getattr(matched_entity, 'status', 'EXPIRED')
        lic_num = getattr(matched_entity, 'license_number', 'N/A')
        
        reasons.append(f"Matched Agency: {matched_entity.name}")
        reasons.append(f"DoFE License Number: {lic_num}")
        reasons.append(f"Government License Status: {status}")
        
        if status == 'ACTIVE':
            if len(suspicious_phrases) > 0:
                reasons.append(f"Caution: Document contains {len(suspicious_phrases)} suspicious phrase(s).")
                return {
                    'verdict': 'SUSPICIOUS',
                    'badge_color': 'yellow',
                    'verdict_title': '🟡 Suspicious — Active Agency with Red Flag Terms',
                    'reasons': reasons,
                    'source_info': 'DoFE Foreign Job Search Portal',
                    'license_status': 'Active License',
                    'is_curated_disclaimer': False,
                }
            else:
                return {
                    'verdict': 'SAFE',
                    'badge_color': 'green',
                    'verdict_title': '🟢 Safe — Licensed & Active DoFE Agency',
                    'reasons': reasons,
                    'source_info': 'DoFE Foreign Job Search Portal',
                    'license_status': 'Active License',
                    'is_curated_disclaimer': False,
                }
        else:
            reasons.append(f"CRITICAL RISK: DoFE License is {status.upper()}. Recruiting workers under an expired/cancelled license is illegal.")
            return {
                'verdict': 'HIGH_RISK',
                'badge_color': 'red',
                'verdict_title': f'🔴 High Risk — Agency License is {status}',
                'reasons': reasons,
                'source_info': 'DoFE Foreign Job Search Portal',
                'license_status': f'License {status}',
                'is_curated_disclaimer': False,
            }
            
    # Default fallback
    return {
        'verdict': 'UNKNOWN',
        'badge_color': 'gray',
        'verdict_title': '⚪ Unknown Status',
        'reasons': ['Unable to verify record status.'],
        'source_info': 'System',
        'license_status': 'N/A',
        'is_curated_disclaimer': False,
    }
