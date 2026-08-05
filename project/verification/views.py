import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.ocr_extractor import extract_text_from_file
from verification.verdicts import verify_agency, verify_consultancy, verify_university
from verification.pipelines import run_offer_letter_pipeline, run_scholarship_letter_pipeline

def serialize_verdict(verdict) -> dict | None:
    if not verdict:
        return None
    return {
        'risk_level': verdict.risk_level,
        'label': verdict.label,
        'source': verdict.source,
        'is_verified_source': verdict.is_verified_source,
        'reasons': verdict.reasons,
        'matched_record': verdict.matched_record
    }


def verify_agency_api(request):
    """
    GET /verify/agency?name=X
    """
    name = request.GET.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Query parameter "name" is required'}, status=400)
        
    verdict = verify_agency(name)
    return JsonResponse(serialize_verdict(verdict))


def verify_consultancy_api(request):
    """
    GET /verify/consultancy?name=X&type=business|education
    """
    name = request.GET.get('name', '').strip()
    c_type = request.GET.get('type', '').strip().lower()

    if not name:
        return JsonResponse({'error': 'Query parameter "name" is required'}, status=400)
    if not c_type:
        return JsonResponse({'error': 'Query parameter "type" is required'}, status=400)
    if c_type not in ['business', 'education']:
        return JsonResponse({'error': 'Query parameter "type" must be either "business" or "education"'}, status=400)

    verdict = verify_consultancy(name, c_type)
    return JsonResponse(serialize_verdict(verdict))


def verify_university_api(request):
    """
    GET /verify/university?name=X
    """
    name = request.GET.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Query parameter "name" is required'}, status=400)
        
    verdict = verify_university(name)
    return JsonResponse(serialize_verdict(verdict))


@csrf_exempt
def verify_offer_letter_api(request):
    """
    POST /verify/offer-letter
    Supports application/json and multipart/form-data.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    raw_text = ""
    # 1. Parse JSON
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8'))
            raw_text = data.get('raw_text', '')
        except Exception:
            pass

    # 2. Parse form-data pasted_text
    if not raw_text:
        raw_text = request.POST.get('pasted_text', '').strip()
        if not raw_text:
            raw_text = request.POST.get('raw_text', '').strip()

    # 3. Parse file upload
    uploaded_file = request.FILES.get('offer_letter_file') or request.FILES.get('file')
    if uploaded_file and not raw_text:
        raw_text = extract_text_from_file(uploaded_file)

    if not raw_text:
        return JsonResponse({'error': 'No text content or file provided for analysis'}, status=400)

    pipeline_result = run_offer_letter_pipeline(raw_text)

    response_data = {
        'final_verdict': pipeline_result['final_verdict'],
        'agency_check': serialize_verdict(pipeline_result['agency_check']),
        'ai_detected_flags': pipeline_result['ai_detected_flags'],
        'evidence': pipeline_result['evidence'],
        'extracted_fields': pipeline_result['extracted_fields']
    }
    return JsonResponse(response_data)


@csrf_exempt
def verify_scholarship_letter_api(request):
    """
    POST /verify/scholarship-letter
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    raw_text = ""
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8'))
            raw_text = data.get('raw_text', '')
        except Exception:
            pass

    if not raw_text:
        raw_text = request.POST.get('pasted_text', '').strip()
        if not raw_text:
            raw_text = request.POST.get('raw_text', '').strip()

    uploaded_file = request.FILES.get('scholarship_letter_file') or request.FILES.get('file')
    if uploaded_file and not raw_text:
        raw_text = extract_text_from_file(uploaded_file)

    if not raw_text:
        return JsonResponse({'error': 'No text content or file provided for analysis'}, status=400)

    pipeline_result = run_scholarship_letter_pipeline(raw_text)

    cons_check = None
    if pipeline_result['consultancy_check']:
        cons_check = {
            'verdict': pipeline_result['consultancy_check']['verdict'],
            'details': serialize_verdict(pipeline_result['consultancy_check']['details'])
        }

    response_data = {
        'final_verdict': pipeline_result['final_verdict'],
        'university_check': serialize_verdict(pipeline_result['university_check']),
        'consultancy_check': cons_check,
        'ai_detected_flags': pipeline_result['ai_detected_flags'],
        'evidence': pipeline_result['evidence'],
        'extracted_fields': pipeline_result['extracted_fields']
    }
    return JsonResponse(response_data)
