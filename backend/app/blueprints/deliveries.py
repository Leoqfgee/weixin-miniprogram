from flask import Blueprint, current_app, g

from ..services.orders import DeliveryService
from ..utils.jwt import auth_required
from ..utils.response import success_response

deliveries_bp = Blueprint("deliveries", __name__)


@deliveries_bp.post("/deliveries/<order_id>/confirm")
@auth_required
def confirm_receipt(order_id):
    data = DeliveryService(current_app.db).confirm_receipt(order_id, g.current_user_id)
    return success_response(data)
