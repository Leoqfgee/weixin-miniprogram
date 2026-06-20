ALLOWED_CAMPUSES = {"东校区", "西校区"}
LEGACY_CAMPUS_MAP = {
    "主校区": "东校区",
}


def is_allowed_campus(value):
    return value in ALLOWED_CAMPUSES


def normalize_campus(value, fallback=""):
    text = (value or "").strip()
    if text in ALLOWED_CAMPUSES:
        return text
    return LEGACY_CAMPUS_MAP.get(text, fallback)
