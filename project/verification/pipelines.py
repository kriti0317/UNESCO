import json
import re
import requests
import os
from django.conf import settings
from verification.verdicts import (
    verify_agency, verify_university, verify_consultancy, get_risk_verdict, Verdict
)

GROQ_KEY = "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"


def call_groq_api(prompt: str) -> dict | None:
    """
    Sends request to Groq API using JSON mode.
    Falls back gracefully if the API fails or is not configured.
    """
    api_key = getattr(settings, 'GROQ_API_KEY', None) or os.environ.get('GROQ_API_KEY') or GROQ_KEY
    if not api_key:
        return None
        
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # We will try llama-3.3-70b-versatile, and fallback to llama-3.1-8b-instant
    for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        try:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }
            res = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=8)
            if res.status_code == 200:
                content = res.json()['choices'][0]['message']['content']
                return json.loads(content)
        except Exception:
            continue
    return None


# ----------------------------------------------------------------------
# TASK 4a - Offer Letter Pipeline
# ----------------------------------------------------------------------

def extract_offer_letter_fields(raw_text: str) -> dict:
    """
    Stage 1 - Extract and flag fields from recruitment offer letter.
    Uses Groq LLM with a fallback regex heuristic parser.
    """
    if not raw_text or not raw_text.strip():
        return {
            "agency_name": "",
            "country": "",
            "salary_mentioned": "",
            "advance_fee_mentioned": False,
            "guarantees_visa_language": False,
            "evidence_quotes": []
        }

    prompt = f"""Extract the following structured JSON fields from the provided recruitment offer letter text.
Do NOT include markdown formatting like ```json ... ```. Return ONLY a valid JSON object.
All evidence quotes must be short (each 15 words or fewer) and must come directly from the text.

JSON structure:
{{
  "agency_name": "exact name of the recruiting/manpower agency mentioned in the letter",
  "country": "destination country",
  "salary_mentioned": "salary details if mentioned, otherwise empty string",
  "advance_fee_mentioned": true/false (true if there is any mention of paying advance fee, processing fee, deposit, or upfront payment),
  "guarantees_visa_language": true/false (true if the text guarantees the visa, job placement, or visa approval),
  "evidence_quotes": ["quote 1", "quote 2"] (list of short quotes showing the evidence for any fee demands or visa guarantees)
}}

Offer Letter Text:
{raw_text[:4000]}"""

    extracted = call_groq_api(prompt)
    if extracted:
        # Normalize and validate keys
        return {
            "agency_name": str(extracted.get("agency_name", "")).strip(),
            "country": str(extracted.get("country", "")).strip(),
            "salary_mentioned": str(extracted.get("salary_mentioned", "")).strip(),
            "advance_fee_mentioned": bool(extracted.get("advance_fee_mentioned", False)),
            "guarantees_visa_language": bool(extracted.get("guarantees_visa_language", False)),
            "evidence_quotes": [str(q).strip() for q in extracted.get("evidence_quotes", []) if len(str(q).split()) <= 15]
        }
        
    # Heuristic Fallback in case of API failure
    return fallback_extract_offer_letter(raw_text)


def fallback_extract_offer_letter(raw_text: str) -> dict:
    text = raw_text.strip()
    agency_name = ""
    org_match = re.search(r'(?:Company|Agency|Organization|Issued\s+By|University|Employer|Ref|From)\s*:\s*([^\n\r,]+)', text, re.IGNORECASE)
    if org_match:
        agency_name = org_match.group(1).strip()
    else:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in lines[:5]:
            if re.search(r'(pvt|ltd|inc|overseas|agency|recruitment|manpower|consultancy)', line, re.IGNORECASE):
                agency_name = line
                break
        if not agency_name and lines:
            agency_name = lines[0]
            
    country = ""
    country_match = re.search(r'\b(Dubai|UAE|Qatar|Saudi Arabia|Malaysia|Kuwait|Bahrain|Oman|Japan|Korea|Australia|UK|United Kingdom|USA|United States|Canada|Nepal|Poland|Romania|Malta|Cyprus)\b', text, re.IGNORECASE)
    if country_match:
        country = country_match.group(1).title()
        
    salary_match = re.search(r'(\$\s*([5-9]\d{3}|[1-9]\d{4,})|salary|payment|per month)\s*([^\n]+)?', text, re.IGNORECASE)
    salary_mentioned = salary_match.group(0).strip() if salary_match else ""
    
    advance_fee_mentioned = False
    guarantees_visa_language = False
    evidence_quotes = []
    
    fee_patterns = [
        r'(advance|upfront|processing|deposit)\s+(fee|payment|money|cost|charge)',
        r'(esewa|khalti|western\s*union|ime\s*pay|moneygram|personal\s*account|personal\s*bank)'
    ]
    for pattern in fee_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            advance_fee_mentioned = True
            evidence_quotes.append(f"Fee term: '{m.group(0)}'")
            
    visa_patterns = [
        r'(100%|guaranteed|direct)\s*(visa|job|employment|placement)',
        r'(no\s+interview|without\s+interview|no\s+skills\s+required)'
    ]
    for pattern in visa_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            guarantees_visa_language = True
            evidence_quotes.append(f"Visa term: '{m.group(0)}'")
            
    return {
        "agency_name": agency_name[:200],
        "country": country[:100],
        "salary_mentioned": salary_mentioned[:150],
        "advance_fee_mentioned": advance_fee_mentioned,
        "guarantees_visa_language": guarantees_visa_language,
        "evidence_quotes": evidence_quotes
    }


def run_offer_letter_pipeline(raw_text: str) -> dict:
    """
    Runs the full 3-Stage recruitment offer letter verification:
    Stage 1: Extract fields (AI)
    Stage 2: Database verify lookup (Deterministic)
    Stage 3: Decision matrix risk assessment (Deterministic)
    """
    # Stage 1: Extraction
    extracted = extract_offer_letter_fields(raw_text)
    
    # Stage 2: DB Lookup
    agency_verdict = verify_agency(extracted["agency_name"])
    
    # Map red flags from extracted fields
    red_flags = []
    if extracted["advance_fee_mentioned"]:
        red_flags.append("Advance fee, processing cost, or security deposit requested in letter.")
    if extracted["guarantees_visa_language"]:
        red_flags.append("Letter contains guaranteed visa, placement, or direct entry language.")

    # Stage 3: Risk Verdict Table
    final_verdict = get_risk_verdict(agency_verdict, red_flags)
    
    return {
        "final_verdict": final_verdict,
        "agency_check": agency_verdict,
        "ai_detected_flags": red_flags,
        "evidence": extracted["evidence_quotes"],
        "extracted_fields": extracted
    }


# ----------------------------------------------------------------------
# TASK 4b - Scholarship / Study Abroad Pipeline
# ----------------------------------------------------------------------

def extract_scholarship_letter_fields(raw_text: str) -> dict:
    """
    Stage 1 - Extract and flag fields from scholarship offer letter.
    """
    if not raw_text or not raw_text.strip():
        return {
            "university_name": "",
            "country": "",
            "scholarship_provider": "",
            "tuition_or_fee_mentioned": False,
            "guarantees_admission_language": False,
            "unrealistic_scholarship_percentage": False,
            "consultancy_name": "",
            "evidence_quotes": []
        }

    prompt = f"""Extract the following structured JSON fields from the provided scholarship or university offer letter text.
Do NOT include markdown formatting like ```json ... ```. Return ONLY a valid JSON object.
All evidence quotes must be short (each 15 words or fewer) and must come directly from the text.

JSON structure:
{{
  "university_name": "exact name of the university or college mentioned in the letter",
  "country": "target study-abroad destination country",
  "scholarship_provider": "name of the provider or sponsoring agency, if any",
  "tuition_or_fee_mentioned": true/false (true if there is any mention of paying tuition, deposit fees, administrative charges, or processing fees),
  "guarantees_admission_language": true/false (true if the text guarantees admission, visa clearance, or scholarship entitlement before institutional review),
  "unrealistic_scholarship_percentage": true/false (true if it promises unrealistic benefits like '100% tuition coverage + guaranteed housing + no application evaluation'),
  "consultancy_name": "name of the education consultancy, consultancy agent, or processing agency mentioned in the text (if any)",
  "evidence_quotes": ["quote 1", "quote 2"] (list of short quotes showing evidence of fees, admission guarantees, or unrealistic percentages)
}}

Scholarship Letter Text:
{raw_text[:4000]}"""

    extracted = call_groq_api(prompt)
    if extracted:
        return {
            "university_name": str(extracted.get("university_name", "")).strip(),
            "country": str(extracted.get("country", "")).strip(),
            "scholarship_provider": str(extracted.get("scholarship_provider", "")).strip(),
            "tuition_or_fee_mentioned": bool(extracted.get("tuition_or_fee_mentioned", False)),
            "guarantees_admission_language": bool(extracted.get("guarantees_admission_language", False)),
            "unrealistic_scholarship_percentage": bool(extracted.get("unrealistic_scholarship_percentage", False)),
            "consultancy_name": str(extracted.get("consultancy_name", "")).strip(),
            "evidence_quotes": [str(q).strip() for q in extracted.get("evidence_quotes", []) if len(str(q).split()) <= 15]
        }

    # Heuristic Fallback in case of API failure
    return fallback_extract_scholarship_letter(raw_text)


def fallback_extract_scholarship_letter(raw_text: str) -> dict:
    text = raw_text.strip()
    university_name = ""
    uni_match = re.search(r'(?:University|College|Institute|School|Academy|Ref|From)\s*:\s*([^\n\r,]+)', text, re.IGNORECASE)
    if uni_match:
        university_name = uni_match.group(1).strip()
    else:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in lines[:5]:
            if re.search(r'(university|college|institute|academy)', line, re.IGNORECASE):
                university_name = line
                break
        if not university_name and lines:
            university_name = lines[0]
            
    country = ""
    country_match = re.search(r'\b(Dubai|UAE|Qatar|Saudi Arabia|Malaysia|Kuwait|Bahrain|Oman|Japan|Korea|Australia|UK|United Kingdom|USA|United States|Canada|Nepal|Poland|Romania|Malta|Cyprus)\b', text, re.IGNORECASE)
    if country_match:
        country = country_match.group(1).title()
        
    consultancy_name = ""
    cons_match = re.search(r'(?:via|processed by|consultancy|agent)\s*:\s*([^\n\r,]+)', text, re.IGNORECASE)
    if cons_match:
        consultancy_name = cons_match.group(1).strip()
    else:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in lines:
            if re.search(r'(consultancy|education foundation|education services|visa services|career advisory)', line, re.IGNORECASE):
                consultancy_name = line
                break
                
    tuition_or_fee_mentioned = False
    guarantees_admission_language = False
    unrealistic_scholarship_percentage = False
    evidence_quotes = []
    
    fee_patterns = [
        r'(processing|security|registration|administrative)\s+fee',
        r'deposit\s+(of|payment)',
        r'(esewa|khalti|western\s*union|personal\s*account)'
    ]
    for pattern in fee_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            tuition_or_fee_mentioned = True
            evidence_quotes.append(f"Fee: '{m.group(0)}'")
            
    adm_patterns = [
        r'(guaranteed|assured|direct)\s*(admission|enrollment|entry)',
        r'admission\s*(is)?\s*guaranteed'
    ]
    for pattern in adm_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            guarantees_admission_language = True
            evidence_quotes.append(f"Guaranteed Admission: '{m.group(0)}'")
            
    pct_patterns = [
        r'100%\s*(scholarship|free|waived)',
        r'(full|fully\s*funded)\s*scholarship\s*(without|no\s+review)'
    ]
    for pattern in pct_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            unrealistic_scholarship_percentage = True
            evidence_quotes.append(f"Scholarship scale: '{m.group(0)}'")
            
    return {
        "university_name": university_name[:200],
        "country": country[:100],
        "scholarship_provider": "",
        "tuition_or_fee_mentioned": tuition_or_fee_mentioned,
        "guarantees_admission_language": guarantees_admission_language,
        "unrealistic_scholarship_percentage": unrealistic_scholarship_percentage,
        "consultancy_name": consultancy_name[:200],
        "evidence_quotes": evidence_quotes
    }


def run_scholarship_letter_pipeline(raw_text: str) -> dict:
    """
    Runs the full 3-Stage study-abroad/scholarship letter verification:
    Stage 1: Extract fields (AI)
    Stage 2: Database lookup of both University and optionally education Consultancy
    Stage 3: Deterministic risk decision
    """
    # Stage 1: Extraction
    extracted = extract_scholarship_letter_fields(raw_text)
    
    # Stage 2: DB Lookups
    university_verdict = verify_university(extracted["university_name"])
    
    consultancy_verdict = None
    if extracted["consultancy_name"]:
        consultancy_verdict = verify_consultancy(extracted["consultancy_name"], consultancy_type="education")
        
    # Map red flags from extracted fields
    red_flags = []
    if extracted["tuition_or_fee_mentioned"]:
        red_flags.append("Upfront processing, security deposit, or administrative fees requested in scholarship offer.")
    if extracted["guarantees_admission_language"]:
        red_flags.append("Letter contains guaranteed admission, enrollment, or entry language.")
    if extracted["unrealistic_scholarship_percentage"]:
        red_flags.append("Contains unrealistic benefit promises (e.g. 100% scholarship without standard application evaluation).")

    # Stage 3: Risk Verdict
    # Call get_risk_verdict once against the primary university check
    primary_verdict = get_risk_verdict(university_verdict, red_flags)
    
    # If a consultancy was mentioned, run its own get_risk_verdict check as well
    consultancy_check_data = None
    if consultancy_verdict:
        # Consultancies are mapped to UNKNOWN in DB check, so get_risk_verdict returns "⚠️ Unknown — Verify Manually"
        # unless they are not listed ("❌ Not Listed"), which maps to "🔴 High Risk"
        consultancy_risk = get_risk_verdict(consultancy_verdict, [])
        consultancy_check_data = {
            "verdict": consultancy_risk,
            "details": consultancy_verdict
        }

    return {
        "final_verdict": primary_verdict,
        "university_check": university_verdict,
        "consultancy_check": consultancy_check_data,
        "ai_detected_flags": red_flags,
        "evidence": extracted["evidence_quotes"],
        "extracted_fields": extracted
    }
