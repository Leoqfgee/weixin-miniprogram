from flask import g, jsonify


def _trace_id() -> str:
    return getattr(g, "trace_id", "")


def success_response(data=None, message="success", http_status=200):
    payload = {
        "code": 0,
        "message": message,
        "data": data if data is not None else {},
        "trace_id": _trace_id(),
    }
    return jsonify(payload), http_status


def error_response(code, message, errors=None, http_status=400):
    payload = {
        "code": code,
        "message": message,
        "errors": errors if errors is not None else [],
        "trace_id": _trace_id(),
    }
    return jsonify(payload), http_status
