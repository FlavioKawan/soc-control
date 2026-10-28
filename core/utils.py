def parse_int_or_none(value):
    """
    Safely turns a raw GET/POST value into an int for use in a pk/id
    lookup, or None if it isn't one - instead of letting a crafted
    querystring (e.g. ?client=abc) blow up the ORM with an unhandled
    ValueError (500, and a stack trace when DEBUG=True).
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
