from flask import Blueprint, current_app, g, request

from ..services.orders import PaymentService
from ..utils.jwt import auth_required
from ..utils.response import success_response

payments_bp = Blueprint("payments", __name__)


@payments_bp.post("/payments/mock-confirm")
@auth_required
def mock_confirm():
    payload = request.get_json(silent=True) or {}
    idempotency_key = request.headers.get("X-Idempotency-Key") or payload.get("idempotency_key")
    data = PaymentService(current_app.db).mock_confirm(g.current_user_id, payload, idempotency_key)
    return success_response(data)
