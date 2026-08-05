import os
import re
import json
import requests
from PIL import Image
from django.conf import settings

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

GROQ_KEY = "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"

RED_FLAG_PATTERNS = [
    (r'(advance|upfront|processing|deposit)\s+(fee|payment|money|cost|charge)', 'Requests advance processing/deposit fee before visa issuance'),
    (r'(esewa|khalti|western\s*union|ime\s*pay|moneygram|personal\s*account|personal\s*bank)', 'Requests payment via personal wallet or Western Union transfer'),
    (r'(100%|guaranteed|direct)\s*(visa|job|employment|placement)', 'Claims guaranteed visa/job placement without official embassy processing'),
    (r'(no\s+interview|without\s+interview|no\s+skills\s+required)', 'Promises employment/visa without interview or skill test'),
    (r'(medical|registration|admission)\s+fee\s+first', 'Demands registration or medical payment before contract signing'),
    (r'@[gG][mM][aA][iI][lL]\.[cC][oO][mM]|@[yY][aA][hH][oO][oO]\.[cC][oO][mM]|@[oO][uU][tT][lL][oO][oO][kK]\.[cC][oO][mM]', 'Uses non-official free email domain (@gmail/@yahoo) for official offer letter'),
    (r'(\$\s*([5-9]\d{3}|[1-9]\d{4,}))\s*(per\s*month|monthly)', 'Promises suspiciously inflated salary for low-skilled positions'),
]

def extract_text_from_file(file_obj):
    """
    Extracts raw text from uploaded image, PDF, or text document file.
    """
    if not file_obj:
        return ""
        
    ext = os.path.splitext(file_obj.name)[1].lower()
    
    # 1. Plain Text / CSV file
    if ext in ['.txt', '.csv']:
        try:
            return file_obj.read().decode('utf-8', errors='ignore')
        except Exception:
            return ""
            
    # 2. PDF File extraction via pypdf
    if ext == '.pdf':
        try:
            if PdfReader:
                reader = PdfReader(file_obj)
                extracted_pages = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        extracted_pages.append(text)
                return "\n".join(extracted_pages)
        except Exception as e:
            print("PDF Extraction Exception:", e)
            
    # 3. Image file processing via PIL & pytesseract
    if ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']:
        try:
            image = Image.open(file_obj)
            if pytesseract:
                try:
                    return pytesseract.image_to_string(image)
                except Exception:
                    pass
        except Exception:
            pass
            
    return ""


def process_offer_letter_text(raw_text):
    """
    Stage 1 Extractor:
    Parses raw_text to extract organization_name, country, and suspicious_phrases list.
    Uses Groq API with your credential to structure fields, with regex fallback.
    """
    if not raw_text or not raw_text.strip():
        return {
            'organization_name': '',
            'country': '',
            'suspicious_phrases': [],
            'extractor_used': 'None (empty input)'
        }
        
    text = raw_text.strip()
    
    # 1. Try Groq LLM Extractor using your Groq API key
    groq_api_key = getattr(settings, 'GROQ_API_KEY', None) or os.environ.get('GROQ_API_KEY') or GROQ_KEY
    if groq_api_key:
        headers = {
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": "application/json"
        }
        prompt = f"""Extract the following structured JSON fields from this offer letter text. Do NOT add markdown codeblocks or extra text. Return strictly valid JSON:
{{
  "organization_name": "exact company, manpower agency, or university name mentioned in header/signature",
  "country": "target destination country",
  "suspicious_phrases": ["list any advance fee demands, eSewa/Khalti/Western Union transfers, guaranteed visas, or unrealistically high salary claims"]
}}

Offer Letter Text:
{text[:3500]}"""

        for model_name in ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]:
            try:
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                }
                res = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=6)
                if res.status_code == 200:
                    content = res.json()['choices'][0]['message']['content']
                    parsed = json.loads(content)
                    return {
                        'organization_name': parsed.get('organization_name', '').strip(),
                        'country': parsed.get('country', '').strip(),
                        'suspicious_phrases': parsed.get('suspicious_phrases', []),
                        'extractor_used': f'Groq LLM Extractor ({model_name})'
                    }
            except Exception:
                continue

    # 2. Rule-based Regex Heuristic Extractor (Fallback)
    detected_phrases = []
    for pattern, flag_desc in RED_FLAG_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            detected_phrases.append(f"{flag_desc} (matched term: '{match.group(0)}')")
            
    # Organization Name extraction heuristic
    org_name = ""
    org_match = re.search(r'(?:Company|Agency|Organization|Issued\s+By|University|Employer|Ref|From)\s*:\s*([^\n\r,]+)', text, re.IGNORECASE)
    if org_match:
        org_name = org_match.group(1).strip()
    else:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in lines[:5]:
            if re.search(r'(pvt|ltd|inc|overseas|agency|recruitment|manpower|consultancy|university|college)', line, re.IGNORECASE):
                org_name = line
                break
        if not org_name and lines:
            org_name = lines[0]

    # Country extraction heuristic
    country = ""
    country_match = re.search(r'\b(Dubai|UAE|Qatar|Saudi Arabia|Malaysia|Kuwait|Bahrain|Oman|Japan|Korea|Australia|UK|United Kingdom|USA|United States|Canada|Nepal|Poland|Romania|Malta|Cyprus)\b', text, re.IGNORECASE)
    if country_match:
        country = country_match.group(1).title()

    return {
        'organization_name': org_name[:200],
        'country': country[:100],
        'suspicious_phrases': detected_phrases,
        'extractor_used': 'Regex Heuristic Extractor'
    }
