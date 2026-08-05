import os
import json
import requests
from django.db.models import Q
from django.conf import settings
from verification.models import Agency, Consultancy, University

SYSTEM_PROMPT = """You are 'Aasha' (Hope), the lively, friendly, and deeply caring AI Safety Assistant for Scam Verifier. You are here to empower Nepali families with clear, warm, encouraging, and accurate guidance regarding foreign employment manpower agencies, education consultancies, foreign universities, and scholarship safety.

YOUR PERSONALITY & TONE:
- Warm, welcoming, empathetic, lively, and encouraging (use friendly emojis like 🌟, 🇳🇵, 🛡️, 💡, 🙏).
- Speak clearly in natural English (or simple Nepali if the user writes in Nepali).
- Keep explanations clear, practical, and easy to understand for families.

CRITICAL HARD RULES YOU MUST STRICTLY OBEY:
1. Base your knowledge strictly on the provided Database Context and Safety Guidance text.
2. NEVER produce or declare a final verdict word ("Safe", "Not Licensed", "High Risk", "Scam") on your own for any organization.
3. If a user asks whether a specific agency or university is genuine or safe, warmly share the database details provided in the context, and enthusiastically remind them: "👉 Please run the official Verification Tool on our main dashboard to get the official, verified verdict badge!"
"""

GUIDANCE_RULES_TEXT = """
General Verification Guidance for Nepal Foreign Employment & Studies:
1. Always check if a Manpower Agency has an ACTIVE license registered with the Department of Foreign Employment (DoFE) at foreignjob.dofe.gov.np before paying any money.
2. Education Consultancies are manually registered businesses and do NOT hold DoFE foreign employment recruitment licenses. They cannot legally charge foreign job recruitment fees.
3. Never pay fees via personal mobile wallets (eSewa, Khalti, IME Pay) or Western Union to individual personal accounts. Always demand official printed receipts from the registered organization's official bank account.
4. Guaranteed visa promises without embassy interview or formal contract signing are a major red flag for fraud.
5. In Nepal, free visa & free ticket (Free Visa, Free Ticket) rules apply to select Gulf & Malaysia employment quotas.
"""

GROQ_KEY = "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"

import re
from verification.fuzzy_matcher import fuzzy_find

STOP_WORDS = {
    'can', 'you', 'tell', 'me', 'about', 'check', 'verify', 'verification', 'is', 'are',
    'the', 'this', 'that', 'for', 'with', 'from', 'what', 'where', 'how', 'which', 'who',
    'please', 'agency', 'consultancy', 'university', 'college', 'safe', 'scam', 'fake',
    'genuine', 'real', 'active', 'status', 'namaste', 'hello', 'hi', 'good', 'info',
    'know', 'want', 'give', 'does', 'have', 'valid', 'licensed'
}


def query_rag_chatbot(user_message):
    """
    Lively RAG Chatbot using keyword and fuzzy entity retrieval over Agency, Consultancy, and University models.
    Queries Groq API with live credential.
    """
    if not user_message or not user_message.strip():
        return "Namaste! 🙏 I am Aasha, your AI safety guide. Ask me anything about checking manpower agencies, consultancies, or foreign university scholarships!"
        
    query = user_message.strip()
    
    # Extract clean words and filter out common conversational stop-words
    all_words = re.findall(r'\w+', query.lower())
    search_kws = [w for w in all_words if len(w) > 2 and w not in STOP_WORDS]
    if not search_kws:
        search_kws = [w for w in all_words if len(w) > 2]
    
    context_blocks = []
    context_blocks.append(f"Safety Guidance Rules:\n{GUIDANCE_RULES_TEXT}")
    
    found_agencies = []
    found_consultancies = []
    found_universities = []

    # 1. Search Agencies (SQL + Fuzzy Fallback)
    if search_kws:
        agency_q = Q()
        for kw in search_kws[:4]:
            agency_q |= Q(name__icontains=kw) | Q(permission_no__icontains=kw)
        agencies = list(Agency.objects.filter(agency_q)[:5])
        found_agencies.extend(agencies)

    if not found_agencies:
        fuzzy_agency, score = fuzzy_find(query, Agency.objects.all(), field="name", threshold=75)
        if fuzzy_agency:
            found_agencies.append(fuzzy_agency)

    if found_agencies:
        ag_str = "\n".join([f"- Agency: {a.name} | License: {a.permission_no} | Status: {a.get_status_display()} | Address: {a.address}" for a in found_agencies])
        context_blocks.append(f"Database Matches (Agencies):\n{ag_str}")

    # 2. Search Consultancies (SQL + Fuzzy Fallback)
    if search_kws:
        cons_q = Q()
        for kw in search_kws[:4]:
            cons_q |= Q(name__icontains=kw)
        consultancies = list(Consultancy.objects.filter(cons_q)[:5])
        found_consultancies.extend(consultancies)

    if not found_consultancies:
        fuzzy_cons, score = fuzzy_find(query, Consultancy.objects.all(), field="name", threshold=75)
        if fuzzy_cons:
            found_consultancies.append(fuzzy_cons)

    if found_consultancies:
        cs_str = "\n".join([f"- Consultancy: {c.name} ({c.get_consultancy_type_display()}) | Address: {c.address} | Notes: {c.notes}" for c in found_consultancies])
        context_blocks.append(f"Database Matches (Consultancies):\n{cs_str}")

    # 3. Search Universities (SQL + Fuzzy Fallback)
    if search_kws:
        uni_q = Q()
        for kw in search_kws[:4]:
            uni_q |= Q(name__icontains=kw) | Q(country__icontains=kw)
        unis = list(University.objects.filter(uni_q)[:5])
        found_universities.extend(unis)

    if not found_universities:
        fuzzy_uni, score = fuzzy_find(query, University.objects.all(), field="name", threshold=75)
        if fuzzy_uni:
            found_universities.append(fuzzy_uni)

    if found_universities:
        u_str = "\n".join([f"- University: {u.name} ({u.country}) | Domain: {u.domain}" for u in found_universities])
        context_blocks.append(f"Database Matches (Universities):\n{u_str}")

    full_context = "\n\n".join(context_blocks)

    # Groq API Call with live credential
    api_key = getattr(settings, 'GROQ_API_KEY', None) or os.environ.get('GROQ_API_KEY') or GROQ_KEY
    
    if api_key:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        prompt = f"User Question: {query}\n\nContext Information:\n{full_context}"

        for model_name in ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]:
            try:
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.5
                }
                res = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=6)
                if res.status_code == 200:
                    reply = res.json()['choices'][0]['message']['content'].strip()
                    if reply:
                        return reply
            except Exception:
                continue

    # Grounded Rule-based Fallback Response
    response = [
        "Namaste! 🙏 Here is the verified safety information from our database:\n",
        full_context if len(context_blocks) > 1 else GUIDANCE_RULES_TEXT,
        "\n👉 Note: To check the official verdict for a specific organization, please run the official Verification Tool on the main dashboard!"
    ]
    return "\n".join(response)

