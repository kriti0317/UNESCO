from rapidfuzz import process, fuzz

def match_entity(query_name, queryset, name_field='name', threshold=85.0):
    """
    Single reusable fuzzy matching engine for all lookups (Agency, Consultancy, University).
    
    Parameters:
        query_name (str): User-inputted name
        queryset (QuerySet or iterable): List/QuerySet of model instances
        name_field (str): Attribute name representing the entity name
        threshold (float): Minimum score percentage (0-100) to consider a match. Default is 85.0.
        
    Returns:
        tuple: (best_matched_instance, ratio_score, is_match)
               If score >= threshold, is_match is True. Otherwise False.
    """
    if not query_name or not query_name.strip():
        return (None, 0.0, False)
        
    query_clean = query_name.strip()
    items = list(queryset)
    
    if not items:
        return (None, 0.0, False)
        
    # Extract string choices paired with the model instance
    choices = [(getattr(item, name_field, ''), item) for item in items if getattr(item, name_field, None)]
    
    if not choices:
        return (None, 0.0, False)
        
    names_list = [c[0] for c in choices]
    
    # Use rapidfuzz extractOne with WRatio for optimal handling of typos, ordering, and punctuation
    result = process.extractOne(query_clean, names_list, scorer=fuzz.WRatio)
    
    if not result:
        return (None, 0.0, False)
        
    matched_name, score, match_index = result
    best_instance = choices[match_index][1]
    
    is_match = (score >= threshold)
    return (best_instance if is_match else None, round(score, 1), is_match)
