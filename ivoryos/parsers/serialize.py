import json


def sanitize_for_json(obj):
    """
    Recursively converts sets and other non-JSON-serializable objects to JSON-friendly types.
    """
    from datetime import datetime, date
    from enum import Enum
    
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(x) for x in obj]
    elif isinstance(obj, set):
        return [sanitize_for_json(x) for x in list(obj)]
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    try:
        json.dumps(obj)
        return obj
    except (TypeError, OverflowError):
        return repr(obj)

def safe_dump(obj):
    return sanitize_for_json(obj)
