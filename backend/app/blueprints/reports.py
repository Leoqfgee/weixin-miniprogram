from flask import Blueprint, current_app, g, request

from ..services.reports import ReportService
from ..utils.jwt import auth_required
from ..utils.response import success_response

reports_bp = Blueprint("reports", __name__)


@reports_bp.post("/reports")
@auth_required
def create_report():
    data = ReportService(current_app.db).create_report(g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data, http_status=201)


@reports_bp.get("/reports/my")
@auth_required
def list_my_reports():
    data = ReportService(current_app.db).list_my_reports(g.current_user_id, request.args)
    return success_response(data)
