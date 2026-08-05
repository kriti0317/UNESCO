import json
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .models import Agency, Consultancy, University, UserProfile, ScamReport, VerificationRecord
from .fuzzy_matcher import match_entity
from .rule_engine import evaluate_verdict
from .ocr_extractor import extract_text_from_file, process_offer_letter_text
from .chatbot import query_rag_chatbot


# ----------------------------------------------------
# 1. Dashboard & Landing
# ----------------------------------------------------
def home_dashboard(request):
    total_agencies = Agency.objects.count()
    total_consultancies = Consultancy.objects.count()
    total_universities = University.objects.count()
    total_verifications = VerificationRecord.objects.count()
    recent_verifications = VerificationRecord.objects.select_related('user')[:5]

    context = {
        'total_agencies': total_agencies,
        'total_consultancies': total_consultancies,
        'total_universities': total_universities,
        'total_verifications': total_verifications,
        'recent_verifications': recent_verifications,
    }
    return render(request, 'main/dashboard.html', context)


# ----------------------------------------------------
# 2. Authentication Views
# ----------------------------------------------------
def signup_view(request):
    if request.method == 'POST':
        full_name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        country = request.POST.get('country', 'Nepal').strip()
        password = request.POST.get('password', '')

        if not email or not password or not full_name:
            return render(request, 'main/signup.html', {'error': 'Please fill in all required fields.'})

        if User.objects.filter(username=email).exists():
            return render(request, 'main/signup.html', {'error': 'User with this email already exists.'})

        user = User.objects.create_user(username=email, email=email, password=password, first_name=full_name)
        UserProfile.objects.create(user=user, phone_number=phone, country=country)
        
        login(request, user)
        return redirect('main:dashboard')

    return render(request, 'main/signup.html')


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', 'main:dashboard')
            return redirect(next_url)
        else:
            return render(request, 'main/login.html', {'error': 'Invalid email or password.'})

    return render(request, 'main/login.html')


def logout_view(request):
    logout(request)
    return redirect('main:dashboard')


# ----------------------------------------------------
# 3. Agency & Consultancy Verification Flow
# ----------------------------------------------------
def verify_agency(request):
    query_name = request.GET.get('query_name', '').strip() or request.POST.get('query_name', '').strip()
    license_number = request.GET.get('license_number', '').strip() or request.POST.get('license_number', '').strip()
    
    result = None
    if query_name:
        # Search Agencies first via 85% fuzzy match
        agencies = Agency.objects.all()
        agency_match, agency_score, agency_found = match_entity(query_name, agencies, name_field='name', threshold=85.0)

        # Search Consultancies via 85% fuzzy match
        consultancies = Consultancy.objects.all()
        consultancy_match, consultancy_score, consultancy_found = match_entity(query_name, consultancies, name_field='name', threshold=85.0)

        best_match = None
        is_matched = False
        entity_type = 'AGENCY'
        score = 0.0

        if agency_found and (agency_score >= consultancy_score):
            best_match = agency_match
            is_matched = True
            entity_type = 'AGENCY'
            score = agency_score
        elif consultancy_found:
            best_match = consultancy_match
            is_matched = True
            entity_type = 'CONSULTANCY'
            score = consultancy_score
        elif agency_score > 0 or consultancy_score > 0:
            score = max(agency_score, consultancy_score)

        verdict_data = evaluate_verdict(
            entity_name=query_name,
            matched_entity=best_match,
            is_matched=is_matched,
            entity_type=entity_type,
            suspicious_phrases=[]
        )

        record = VerificationRecord.objects.create(
            user=request.user if request.user.is_authenticated else None,
            verification_type=entity_type,
            input_name=query_name,
            matched_entity_name=best_match.name if best_match else '',
            matched_entity_type=entity_type if best_match else '',
            license_status=verdict_data['license_status'],
            match_score=score,
            verdict=verdict_data['verdict'],
            verdict_display=verdict_data['verdict_title'],
            reasons=verdict_data['reasons'],
            source_info=verdict_data['source_info']
        )

        result = {
            'record_uuid': str(record.uuid),
            'input_name': query_name,
            'is_matched': is_matched,
            'match_score': score,
            'matched_entity': best_match,
            'verdict_data': verdict_data,
        }

    return render(request, 'main/verify_agency.html', {'query_name': query_name, 'result': result})


# ----------------------------------------------------
# 4. University Verification Flow
# ----------------------------------------------------
def verify_university(request):
    university_name = request.GET.get('university_name', '').strip() or request.POST.get('university_name', '').strip()
    country = request.GET.get('country', '').strip() or request.POST.get('country', '').strip()

    result = None
    if university_name:
        unis = University.objects.all()
        if country:
            unis = unis.filter(country__icontains=country)
            
        uni_match, score, is_matched = match_entity(university_name, unis, name_field='name', threshold=85.0)

        verdict_data = evaluate_verdict(
            entity_name=university_name,
            matched_entity=uni_match,
            is_matched=is_matched,
            entity_type='UNIVERSITY',
            suspicious_phrases=[]
        )

        record = VerificationRecord.objects.create(
            user=request.user if request.user.is_authenticated else None,
            verification_type='UNIVERSITY',
            input_name=university_name,
            country=country,
            matched_entity_name=uni_match.name if uni_match else '',
            matched_entity_type='UNIVERSITY' if uni_match else '',
            license_status=verdict_data['license_status'],
            match_score=score,
            verdict=verdict_data['verdict'],
            verdict_display=verdict_data['verdict_title'],
            reasons=verdict_data['reasons'],
            source_info=verdict_data['source_info']
        )

        result = {
            'record_uuid': str(record.uuid),
            'university_name': university_name,
            'country': country,
            'is_matched': is_matched,
            'match_score': score,
            'matched_entity': uni_match,
            'verdict_data': verdict_data,
        }

    return render(request, 'main/verify_university.html', {'university_name': university_name, 'country': country, 'result': result})


# ----------------------------------------------------
# 5. Offer Letter Upload & 3-Stage Verification Pipeline
# ----------------------------------------------------
def verify_offer_letter(request):
    result = None
    if request.method == 'POST':
        raw_text_input = request.POST.get('pasted_text', '').strip()
        uploaded_file = request.FILES.get('offer_letter_file')

        raw_text = raw_text_input
        if uploaded_file and not raw_text:
            raw_text = extract_text_from_file(uploaded_file)

        # Stage 1: Text & Phrase Extraction (AI / Regex)
        extracted = process_offer_letter_text(raw_text)
        org_name = extracted['organization_name']
        extracted_country = extracted['country']
        suspicious_phrases = extracted['suspicious_phrases']

        # Stage 2: Database Match
        best_match = None
        is_matched = False
        score = 0.0
        entity_type = 'OFFER_LETTER'

        if org_name:
            # Check Agencies first
            ag_match, ag_score, ag_found = match_entity(org_name, Agency.objects.all(), name_field='name', threshold=85.0)
            # Check Consultancies
            cs_match, cs_score, cs_found = match_entity(org_name, Consultancy.objects.all(), name_field='name', threshold=85.0)
            # Check Universities
            un_match, un_score, un_found = match_entity(org_name, University.objects.all(), name_field='name', threshold=85.0)

            if ag_found:
                best_match, score, is_matched, entity_type = ag_match, ag_score, True, 'AGENCY'
            elif cs_found:
                best_match, score, is_matched, entity_type = cs_match, cs_score, True, 'CONSULTANCY'
            elif un_found:
                best_match, score, is_matched, entity_type = un_match, un_score, True, 'UNIVERSITY'

        # Stage 3: Fixed Deterministic Rule Engine Decision Table
        verdict_data = evaluate_verdict(
            entity_name=org_name,
            matched_entity=best_match,
            is_matched=is_matched,
            entity_type=entity_type,
            suspicious_phrases=suspicious_phrases
        )

        # Save record (PRIVACY SAFE: No raw_text stored!)
        record = VerificationRecord.objects.create(
            user=request.user if request.user.is_authenticated else None,
            verification_type='OFFER_LETTER',
            input_name=org_name or 'Uploaded Document',
            country=extracted_country,
            matched_entity_name=best_match.name if best_match else '',
            matched_entity_type=entity_type if best_match else '',
            license_status=verdict_data['license_status'],
            match_score=score,
            verdict=verdict_data['verdict'],
            verdict_display=verdict_data['verdict_title'],
            suspicious_phrases=suspicious_phrases,
            reasons=verdict_data['reasons'],
            source_info=verdict_data['source_info']
        )

        result = {
            'record_uuid': str(record.uuid),
            'extracted_org': org_name,
            'extracted_country': extracted_country,
            'suspicious_phrases': suspicious_phrases,
            'extractor_used': extracted['extractor_used'],
            'matched_entity': best_match,
            'is_matched': is_matched,
            'verdict_data': verdict_data,
        }

    return render(request, 'main/verify_offer_letter.html', {'result': result})


# ----------------------------------------------------
# 6. Report Scam Action (Mocked Ministry Email Alert)
# ----------------------------------------------------
def report_scam(request):
    if request.method == 'POST':
        entity_name = request.POST.get('entity_name', 'Unknown')
        entity_type = request.POST.get('entity_type', 'General')
        reason = request.POST.get('reason', '')
        user_phone = request.POST.get('phone', '')
        user_email = request.POST.get('email', '')

        if request.user.is_authenticated:
            user_phone = user_phone or getattr(request.user.profile, 'phone_number', '')
            user_email = user_email or request.user.email

        report = ScamReport.objects.create(
            user=request.user if request.user.is_authenticated else None,
            reported_entity_name=entity_name,
            entity_type=entity_type,
            user_phone=user_phone,
            user_email=user_email,
            reason=reason,
            email_sent=settings.ENABLE_MINISTRY_EMAIL_ALERT
        )

        tracking_id = f"SR-MOHA-{report.id:05d}"

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'tracking_id': tracking_id,
                'email_sent': settings.ENABLE_MINISTRY_EMAIL_ALERT,
                'message': 'Scam report successfully submitted and logged for government review.'
            })

        return render(request, 'main/report_submitted.html', {
            'tracking_id': tracking_id,
            'report': report,
            'email_sent': settings.ENABLE_MINISTRY_EMAIL_ALERT
        })

    return redirect('main:dashboard')


# ----------------------------------------------------
# 7. Shareable Verdict Card (Public URL)
# ----------------------------------------------------
def shareable_verdict_card(request, record_uuid):
    record = get_object_or_404(VerificationRecord, uuid=record_uuid)
    
    context = {
        'record': record,
        'full_url': request.build_absolute_uri(),
    }
    return render(request, 'main/verdict_card.html', context)


# ----------------------------------------------------
# 8. Grounded RAG Chatbot API
# ----------------------------------------------------
@csrf_exempt
def chatbot_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            message = data.get('message', '')
        except Exception:
            message = request.POST.get('message', '')

        reply = query_rag_chatbot(message)
        return JsonResponse({'reply': reply})
        
    return JsonResponse({'error': 'POST method required'}, status=405)
