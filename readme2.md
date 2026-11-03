
1. Find this function, about 20 lines below the KEYS = (...) block:


def kind(exc: Exception) -> str:
    text = str(exc).lower()
    found = [name for name, words in KEYS if any(word in text for word in words)]
    return type(exc).__name__ + (" [" + ", ".join(found) + "]" if found else "")
2. Replace those 4 lines with these 13:


def kind(exc: Exception) -> str:
    code = None
    for method in ("getCondition", "getErrorClass"):
        try:
            code = getattr(exc, method)()
        except Exception:
            code = None
        if code:
            break
    text = str(exc).lower()
    found = [name for name, words in KEYS if any(word in text for word in words)]
    return (type(exc).__name__ + (f" {code}" if code else "")
            + (" [" + ", ".join(found) + "]" if found else ""))
