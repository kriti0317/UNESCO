import json
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from verification.models import Agency, Consultancy, University
from .models import UserProfile, ScamReport, VerificationRecord
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
    check_type = request.GET.get('check_type', 'all').strip().lower()
    
    result = None
    if query_name:
        from verification.fuzzy_matcher import fuzzy_find
        from verification.verdicts import verify_agency as core_verify_agency
        from verification.verdicts import verify_consultancy as core_verify_consultancy

        best_agency = None
        ag_score = 0
        best_consultancy = None
        cs_score = 0

        # Search based on check_type
        if check_type in ['all', 'agency']:
            best_agency, ag_score = fuzzy_find(query_name, Agency.objects.all(), field="name")
        
        if check_type in ['all', 'education', 'business']:
            c_qs = Consultancy.objects.all()
            if check_type == 'education':
                c_qs = c_qs.filter(consultancy_type='education')
            elif check_type == 'business':
                c_qs = c_qs.filter(consultancy_type='business')
            best_consultancy, cs_score = fuzzy_find(query_name, c_qs, field="name")

        best_match = None
        is_matched = False
        entity_type = 'AGENCY'
        score = 0.0

        if best_agency and (ag_score >= cs_score):
            best_match = best_agency
            is_matched = True
            entity_type = 'AGENCY'
            score = ag_score
        elif best_consultancy:
            best_match = best_consultancy
            is_matched = True
            entity_type = 'CONSULTANCY'
            score = cs_score
        elif ag_score > 0 or cs_score > 0:
            score = max(ag_score, cs_score)

        # Get core verdict
        if entity_type == 'AGENCY':
            verdict_obj = core_verify_agency(query_name)
        else:
            c_type = best_match.consultancy_type if best_match else ("business" if check_type == 'business' else "education")
            verdict_obj = core_verify_consultancy(query_name, consultancy_type=c_type)

        # Map to dict structure expected by template
        badge_color = 'gray'
        if verdict_obj.risk_level == 'SAFE':
            badge_color = 'green'
        elif verdict_obj.risk_level == 'SUSPICIOUS':
            badge_color = 'yellow'
        elif verdict_obj.risk_level == 'HIGH_RISK':
            badge_color = 'red'

        verdict_title = verdict_obj.label
        if verdict_obj.risk_level == 'SAFE':
            verdict_title = f"🟢 {verdict_obj.label}"
        elif verdict_obj.risk_level == 'SUSPICIOUS':
            verdict_title = f"🟡 {verdict_obj.label}"
        elif verdict_obj.risk_level == 'HIGH_RISK':
            verdict_title = f"🔴 {verdict_obj.label}"
        else:
            verdict_title = f"⚪ {verdict_obj.label}"

        verdict_data = {
            'verdict': verdict_obj.risk_level,
            'badge_color': badge_color,
            'verdict_title': verdict_title,
            'reasons': verdict_obj.reasons,
            'source_info': 'DoFE Foreign Job Search Portal' if entity_type == 'AGENCY' else (best_match.source_note if best_match else ''),
            'license_status': 'Active License' if (entity_type == 'AGENCY' and best_match and best_match.status == 'active') else ('Not Licensed' if not is_matched else 'Curated Record'),
            'is_curated_disclaimer': (entity_type == 'CONSULTANCY' and is_matched),
        }

        record = VerificationRecord.objects.create(
            user=request.user if request.user.is_authenticated else None,
            verification_type=entity_type,
            input_name=query_name,
            matched_entity_name=best_match.name if best_match else '',
            matched_entity_type=entity_type if best_match else '',
            license_status=verdict_data['license_status'],
            match_score=score,
            verdict=verdict_obj.risk_level,
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

    return render(request, 'main/verify_agency.html', {'query_name': query_name, 'check_type': check_type, 'result': result})


def verify_university(request):
    university_name = request.GET.get('university_name', '').strip() or request.POST.get('university_name', '').strip()
    country = request.GET.get('country', '').strip() or request.POST.get('country', '').strip()

    result = None
    if university_name:
        unis = University.objects.all()
        if country:
            unis = unis.filter(country__icontains=country)
            
        from verification.fuzzy_matcher import fuzzy_find
        from verification.verdicts import verify_university as core_verify_university

        uni_match, score = fuzzy_find(university_name, unis, field="name")
        is_matched = uni_match is not None

        # Get core verdict
        verdict_obj = core_verify_university(university_name)

        badge_color = 'gray'
        if verdict_obj.risk_level == 'SAFE':
            badge_color = 'green'
        elif verdict_obj.risk_level == 'SUSPICIOUS':
            badge_color = 'yellow'
        elif verdict_obj.risk_level == 'HIGH_RISK':
            badge_color = 'red'

        verdict_title = verdict_obj.label
        if verdict_obj.risk_level == 'SAFE':
            verdict_title = f"🟢 {verdict_obj.label}"
        elif verdict_obj.risk_level == 'SUSPICIOUS':
            verdict_title = f"🟡 {verdict_obj.label}"
        elif verdict_obj.risk_level == 'HIGH_RISK':
            verdict_title = f"🔴 {verdict_obj.label}"
        else:
            verdict_title = f"⚪ {verdict_obj.label}"

        verdict_data = {
            'verdict': verdict_obj.risk_level,
            'badge_color': badge_color,
            'verdict_title': verdict_title,
            'reasons': verdict_obj.reasons,
            'source_info': 'Hipolabs/Wikipedia',
            'license_status': 'Recognized Institution',
            'is_curated_disclaimer': False,
        }

        record = VerificationRecord.objects.create(
            user=request.user if request.user.is_authenticated else None,
            verification_type='UNIVERSITY',
            input_name=university_name,
            country=country,
            matched_entity_name=uni_match.name if uni_match else '',
            matched_entity_type='UNIVERSITY' if uni_match else '',
            license_status=verdict_data['license_status'],
            match_score=score,
            verdict=verdict_obj.risk_level,
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


def verify_offer_letter(request):
    result = None
    if request.method == 'POST':
        raw_text_input = request.POST.get('pasted_text', '').strip()
        uploaded_file = request.FILES.get('offer_letter_file')

        raw_text = raw_text_input
        if uploaded_file and not raw_text:
            raw_text = extract_text_from_file(uploaded_file)

        from verification.pipelines import run_offer_letter_pipeline
        from verification.fuzzy_matcher import fuzzy_find

        # Run Stage 1/2/3 pipeline
        pipeline_result = run_offer_letter_pipeline(raw_text)
        
        extracted = pipeline_result['extracted_fields']
        org_name = extracted['agency_name']
        extracted_country = extracted['country']
        suspicious_phrases = pipeline_result['ai_detected_flags'] + pipeline_result['evidence']

        # Check DB matching agency for UI context
        best_match, score = fuzzy_find(org_name, Agency.objects.all(), field="name")
        is_matched = best_match is not None
        entity_type = 'AGENCY'

        agency_verdict = pipeline_result['agency_check']
        badge_color = 'gray'
        if agency_verdict.risk_level == 'SAFE':
            badge_color = 'green'
        elif agency_verdict.risk_level == 'SUSPICIOUS':
            badge_color = 'yellow'
        elif agency_verdict.risk_level == 'HIGH_RISK':
            badge_color = 'red'

        verdict_title = agency_verdict.label
        if agency_verdict.risk_level == 'SAFE':
            verdict_title = f"🟢 {agency_verdict.label}"
        elif agency_verdict.risk_level == 'SUSPICIOUS':
            verdict_title = f"🟡 {agency_verdict.label}"
        elif agency_verdict.risk_level == 'HIGH_RISK':
            verdict_title = f"🔴 {agency_verdict.label}"
        else:
            verdict_title = f"⚪ {agency_verdict.label}"

        verdict_data = {
            'verdict': agency_verdict.risk_level,
            'badge_color': badge_color,
            'verdict_title': verdict_title,
            'reasons': agency_verdict.reasons,
            'source_info': 'DoFE Foreign Job Search Portal',
            'license_status': 'Active License' if (best_match and best_match.status == 'active') else ('Not Licensed' if not is_matched else 'Expired/Cancelled'),
            'is_curated_disclaimer': False,
        }

        # Save record
        record = VerificationRecord.objects.create(
            user=request.user if request.user.is_authenticated else None,
            verification_type='OFFER_LETTER',
            input_name=org_name or 'Uploaded Document',
            country=extracted_country,
            matched_entity_name=best_match.name if best_match else '',
            matched_entity_type='AGENCY' if best_match else '',
            license_status=verdict_data['license_status'],
            match_score=score,
            verdict=agency_verdict.risk_level,
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
            'extractor_used': 'Groq LLM Extractor' if getattr(settings, 'GROQ_API_KEY', None) else 'Regex Heuristic Extractor',
            'matched_entity': best_match,
            'is_matched': is_matched,
            'verdict_data': verdict_data,
        }

    return render(request, 'main/verify_offer_letter.html', {'result': result})


def verify_scholarship_letter(request):
    result = None
    if request.method == 'POST':
        raw_text_input = request.POST.get('pasted_text', '').strip()
        uploaded_file = request.FILES.get('scholarship_letter_file')

        raw_text = raw_text_input
        if uploaded_file and not raw_text:
            raw_text = extract_text_from_file(uploaded_file)

        from verification.pipelines import run_scholarship_letter_pipeline
        from verification.fuzzy_matcher import fuzzy_find

        # Run pipeline
        pipeline_result = run_scholarship_letter_pipeline(raw_text)

        extracted = pipeline_result['extracted_fields']
        uni_name = extracted['university_name']
        extracted_country = extracted['country']
        suspicious_phrases = pipeline_result['ai_detected_flags'] + pipeline_result['evidence']

        # Find university in DB
        matched_uni, score = fuzzy_find(uni_name, University.objects.all(), field="name")
        uni_is_matched = matched_uni is not None

        university_verdict = pipeline_result['university_check']
        badge_color = 'gray'
        if university_verdict.risk_level == 'SAFE':
            badge_color = 'green'
        elif university_verdict.risk_level == 'SUSPICIOUS':
            badge_color = 'yellow'
        elif university_verdict.risk_level == 'HIGH_RISK':
            badge_color = 'red'

        verdict_title = university_verdict.label
        if university_verdict.risk_level == 'SAFE':
            verdict_title = f"🟢 {university_verdict.label}"
        elif university_verdict.risk_level == 'SUSPICIOUS':
            verdict_title = f"🟡 {university_verdict.label}"
        elif university_verdict.risk_level == 'HIGH_RISK':
            verdict_title = f"🔴 {university_verdict.label}"
        else:
            verdict_title = f"⚪ {university_verdict.label}"

        verdict_data = {
            'verdict': university_verdict.risk_level,
            'badge_color': badge_color,
            'verdict_title': verdict_title,
            'reasons': university_verdict.reasons,
            'source_info': 'Hipolabs/Wikipedia',
            'license_status': 'Recognized Institution',
            'is_curated_disclaimer': False,
        }

        # Save record
        record = VerificationRecord.objects.create(
            user=request.user if request.user.is_authenticated else None,
            verification_type='SCHOLARSHIP_LETTER',
            input_name=uni_name or 'Uploaded Document',
            country=extracted_country,
            matched_entity_name=matched_uni.name if matched_uni else '',
            matched_entity_type='UNIVERSITY' if matched_uni else '',
            license_status=verdict_data['license_status'],
            match_score=score,
            verdict=university_verdict.risk_level,
            verdict_display=verdict_data['verdict_title'],
            suspicious_phrases=suspicious_phrases,
            reasons=verdict_data['reasons'],
            source_info=verdict_data['source_info']
        )

        result = {
            'record_uuid': str(record.uuid),
            'extracted_uni': uni_name,
            'extracted_country': extracted_country,
            'suspicious_phrases': suspicious_phrases,
            'extractor_used': 'Groq LLM Extractor' if getattr(settings, 'GROQ_API_KEY', None) else 'Regex Heuristic Extractor',
            'matched_uni': matched_uni,
            'uni_is_matched': uni_is_matched,
            'cons_check_data': pipeline_result['consultancy_check'],
            'verdict_data': verdict_data,
            'extracted_fields': extracted,
        }

    return render(request, 'main/verify_scholarship_letter.html', {'result': result})


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
