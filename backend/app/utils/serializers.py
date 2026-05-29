from datetime import datetime

from bson import ObjectId


def to_object_id(value, field_name="id"):
    from .errors import ValidationError

    if not ObjectId.is_valid(str(value)):
        raise ValidationError("参数校验失败", [{"field": field_name, "message": "ID 格式不正确"}])
    return ObjectId(str(value))


def serialize_value(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}
    return value


def serialize_doc(doc):
    if not doc:
        return None
    data = serialize_value(doc)
    if "_id" in data:
        data["id"] = data.pop("_id")
    return data
