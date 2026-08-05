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

def query_rag_chatbot(user_message):
    """
    Lively RAG Chatbot using keyword retrieval over Agency, Consultancy, and University models.
    Queries Groq API with live credential.
    """
    if not user_message or not user_message.strip():
        return "Namaste! 🙏 I am Aasha, your AI safety guide. Ask me anything about checking manpower agencies, consultancies, or foreign university scholarships!"
        
    query = user_message.strip()
    keywords = [w for w in query.split() if len(w) > 2]
    
    context_blocks = []
    context_blocks.append(f"Safety Guidance Rules:\n{GUIDANCE_RULES_TEXT}")
    
    # Keyword SQL Retrieval over local database
    if keywords:
        # 1. Search Agencies
        agency_q = Q()
        for kw in keywords[:3]:
            agency_q |= Q(name__icontains=kw) | Q(license_number__icontains=kw)
        agencies = Agency.objects.filter(agency_q)[:5]
        if agencies:
            ag_str = "\n".join([f"- Agency: {a.name} | License: {a.license_number or 'N/A'} | Status: {a.get_status_display()} | Address: {a.address}" for a in agencies])
            context_blocks.append(f"Database Matches (Agencies):\n{ag_str}")

        # 2. Search Consultancies
        cons_q = Q()
        for kw in keywords[:3]:
            cons_q |= Q(name__icontains=kw)
        consultancies = Consultancy.objects.filter(cons_q)[:5]
        if consultancies:
            cs_str = "\n".join([f"- Consultancy: {c.name} | Status: {c.status} ({c.source_note}) | Address: {c.address}" for c in consultancies])
            context_blocks.append(f"Database Matches (Consultancies):\n{cs_str}")

        # 3. Search Universities
        uni_q = Q()
        for kw in keywords[:3]:
            uni_q |= Q(name__icontains=kw) | Q(country__icontains=kw)
        unis = University.objects.filter(uni_q)[:5]
        if unis:
            u_str = "\n".join([f"- University: {u.name} ({u.country}) | Recognized: {u.recognized} | Source: {u.source}" for u in unis])
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
