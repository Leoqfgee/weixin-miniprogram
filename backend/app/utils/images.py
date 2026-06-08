COS_HOST_MARKER = "campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com"
LEGACY_HOST_MARKERS = ("124.223.146.85",)


def normalize_image_url(url):
    value = str(url or "").strip()
    if not value:
        return ""
    if COS_HOST_MARKER in value:
        return value
    if "tcloudbase.com/uploads/" in value:
        return ""
    if "flask-fnnj" in value and "/uploads/" in value:
        return ""
    if value.startswith("/uploads/demo/"):
        return ""
    if value.startswith("/uploads/"):
        return ""
    if any(marker in value for marker in LEGACY_HOST_MARKERS):
        return ""
    if value.startswith("http://"):
        return ""
    return value


def normalize_image_list(urls):
    return [item for item in (normalize_image_url(url) for url in (urls or [])) if item]
