from rapidfuzz import process, fuzz

FUZZY_THRESHOLD = 85.0

def fuzzy_find(query: str, queryset, field="name", threshold=FUZZY_THRESHOLD):
    """
    Returns (best_match_object, score) or (None, 0) if nothing clears the threshold.
    Matches dynamically against the specified field (default "name").
    
    Uses rapidfuzz WRatio scorer to handle typos, word order, and partial name variations.
    This function is source-agnostic and works for Agency, Consultancy, or University.
    """
    if not query or not query.strip():
        return None, 0

    query_str = query.strip()
    items = list(queryset)
    if not items:
        return None, 0

    choices = [(getattr(item, field, ''), item) for item in items if getattr(item, field, None)]
    if not choices:
        return None, 0

    names = [c[0] for c in choices]
    result = process.extractOne(query_str, names, scorer=fuzz.WRatio)

    if not result:
        return None, 0

    matched_name, score, idx = result
    if score >= threshold:
        return choices[idx][1], round(score, 1)

    return None, round(score, 1)

