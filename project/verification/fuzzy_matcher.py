import rapidfuzz

FUZZY_THRESHOLD = 85

def fuzzy_find(query: str, queryset, field="name", threshold=FUZZY_THRESHOLD):
    """
    Returns (best_match_object, score) or (None, 0) if nothing clears the threshold.
    Matches dynamically against the specified field (default "name").
    
    This function is source-agnostic and works for Agency, Consultancy, or University.
    """
    if not query or not query.strip():
        return None, 0
        
    query_str = query.strip().lower()
    best_match_obj = None
    best_score = 0
    
    # Iterate through queryset objects and calculate similarity score
    for obj in queryset:
        val = getattr(obj, field, "")
        if val:
            score = rapidfuzz.fuzz.ratio(query_str, str(val).strip().lower())
            if score > best_score:
                best_score = score
                best_match_obj = obj
                
    if best_score >= threshold:
        return best_match_obj, best_score
        
    return None, 0
