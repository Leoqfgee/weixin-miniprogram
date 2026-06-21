from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from pymongo import DESCENDING

from ..repositories.products import ProductRepository
from ..repositories.users import UserRepository
from ..utils.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from ..utils.images import normalize_image_list, normalize_image_url
from ..utils.serializers import serialize_doc, to_object_id
from .credit import CreditService, default_credit_deduct


REPORT_STATUS_TEXT = {"pending": "待处理", "approved": "举报成立", "rejected": "未发现违规", "malicious": "恶意举报"}
REPORT_REASON_TEXT = {
    "fake_info": "虚假商品/描述不符",
    "abnormal_price": "价格异常/诱导交易",
    "prohibited": "违禁品/违规内容",
    "infringement": "盗图/侵犯权益",
    "spam": "垃圾广告/重复发布",
    "harassment": "辱骂骚扰/不当言论",
    "fraud": "欺诈风险",
    "other": "其他",
}


def utc_now():
    return datetime.now(timezone.utc)


class ReportService:
    def __init__(self, db):
        self.db = db
        self.products = ProductRepository(db)
        self.users = UserRepository(db)
        self.credit = CreditService(db)

    def create_report(self, reporter_id, payload):
        product_id = to_object_id(payload.get("product_id"), "product_id")
        product = self.products.find_by_id(product_id)
        if not product or product.get("deleted_at"):
            raise NotFoundError("商品不存在")
        if str(product.get("seller_id")) == str(reporter_id):
            raise ForbiddenError("卖家本人不能举报自己的商品")
        if self.db.reports.find_one({"product_id": product_id, "reporter_id": ObjectId(str(reporter_id)), "status": "pending"}):
            raise ConflictError("你已提交过该商品的待处理举报")

        reason_type = (payload.get("reason_type") or "").strip()
        if reason_type not in REPORT_REASON_TEXT:
            raise ValidationError("参数校验失败", [{"field": "reason_type", "message": "请选择举报原因"}])
        description = (payload.get("description") or "").strip()
        if len(description) > 200:
            raise ValidationError("参数校验失败", [{"field": "description", "message": "补充说明最多 200 字"}])
        evidence_images = payload.get("evidence_images") or []
        if not isinstance(evidence_images, list) or len(evidence_images) > 3:
            raise ValidationError("参数校验失败", [{"field": "evidence_images", "message": "凭证图片最多 3 张"}])

        seller = self.users.find_by_id(product["seller_id"]) or {}
        seller_profile = self.users.find_profile(product["seller_id"]) or {}
        reporter = self.users.find_by_id(reporter_id) or {}
        reporter_profile = self.users.find_profile(reporter_id) or {}
        images = normalize_image_list(product.get("images") or [])
        doc = {
            "report_no": f"RP{utc_now().strftime('%Y%m%d%H%M%S')}{uuid4().hex[:6].upper()}",
            "product_id": product["_id"],
            "product_title_snapshot": product.get("title", ""),
            "product_image_snapshot": normalize_image_url(product.get("cover_image")) or (images[0] if images else ""),
            "seller_id": product["seller_id"],
            "seller_nickname_snapshot": seller_profile.get("nickname") or seller.get("nickname") or "校园用户",
            "reporter_id": ObjectId(str(reporter_id)),
            "reporter_nickname_snapshot": reporter_profile.get("nickname") or reporter.get("nickname") or "校园用户",
            "reason_type": reason_type,
            "reason_text": REPORT_REASON_TEXT[reason_type],
            "description": description,
            "evidence_images": evidence_images,
            "status": "pending",
            "admin_id": None,
            "admin_note": "",
            "credit_deduct": 0,
            "product_action": "none",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "handled_at": None,
        }
        result = self.db.reports.insert_one(doc)
        self._notify_admin_pending(result.inserted_id)
        return self._present(self.db.reports.find_one({"_id": result.inserted_id}))

    def list_my_reports(self, user_id, args):
        return self._list({"reporter_id": ObjectId(str(user_id))}, args)

    def list_admin_reports(self, args):
        query = {}
        status = (args.get("status") or "").strip()
        if status:
            if status not in REPORT_STATUS_TEXT:
                raise ValidationError("参数校验失败", [{"field": "status", "message": "举报状态不合法"}])
            query["status"] = status
        data = self._list(query, args)
        data["pending_count"] = self.db.reports.count_documents({"status": "pending"})
        return data

    def get_admin_report(self, report_id):
        return self._present(self._get_report(report_id), detail=True)

    def handle_report(self, report_id, admin_user, payload):
        report = self._get_report(report_id)
        if report["status"] != "pending":
            raise ConflictError("当前举报已处理")
        result = (payload.get("result") or payload.get("status") or "").strip()
        if result not in {"approved", "rejected", "malicious"}:
            raise ValidationError("参数校验失败", [{"field": "result", "message": "处理结果不合法"}])
        admin_note = (payload.get("admin_note") or payload.get("reason") or "").strip()
        credit_deduct = payload.get("credit_deduct")
        if credit_deduct in {None, ""}:
            credit_deduct = default_credit_deduct(report.get("reason_type")) if result == "approved" else (5 if result == "malicious" else 0)
        try:
            credit_deduct = max(0, int(credit_deduct))
        except (TypeError, ValueError) as exc:
            raise ValidationError("参数校验失败", [{"field": "credit_deduct", "message": "扣分值必须是整数"}]) from exc

        product_action = "none"
        if result == "approved":
            self.products.update_fields(report["product_id"], {"status": "taken_down", "taken_down_reason": "report_approved", "taken_down_report_id": report["_id"], "stock": 0})
            product_action = "taken_down"
            if credit_deduct:
                self.credit.adjust(report["seller_id"], -credit_deduct, "deduct", report.get("reason_type") or "other", f"举报成立：{report.get('reason_text')}", operator_type="admin", operator_id=admin_user["_id"], related_report_id=report["_id"], related_product_id=report["product_id"])
            self._notify_user(report["seller_id"], "product_taken_down_by_report", f"你的商品因举报成立已被下架，信用分扣除 {credit_deduct} 分", report, admin_user["_id"])
            self._notify_user(report["reporter_id"], "report_approved", "你提交的举报已处理，举报成立", report, admin_user["_id"])
        elif result == "rejected":
            self._notify_user(report["reporter_id"], "report_rejected", "你提交的举报已处理，未发现违规", report, admin_user["_id"])
        elif result == "malicious":
            if credit_deduct:
                self.credit.adjust(report["reporter_id"], -credit_deduct, "deduct", "malicious_report", "恶意举报扣分", operator_type="admin", operator_id=admin_user["_id"], related_report_id=report["_id"], related_product_id=report["product_id"])
            self._notify_user(report["reporter_id"], "report_malicious", f"你的举报被判定为恶意举报，信用分扣除 {credit_deduct} 分", report, admin_user["_id"])

        self.db.reports.update_one(
            {"_id": report["_id"]},
            {"$set": {"status": result, "admin_id": admin_user["_id"], "admin_note": admin_note, "credit_deduct": credit_deduct, "product_action": product_action, "handled_at": utc_now(), "updated_at": utc_now()}},
        )
        return self._present(self._get_report(report["_id"]), detail=True)

    def _list(self, query, args):
        page = max(int(args.get("page", 1)), 1)
        page_size = min(max(int(args.get("page_size", 20)), 1), 50)
        total = self.db.reports.count_documents(query)
        items = list(self.db.reports.find(query).sort("created_at", DESCENDING).skip((page - 1) * page_size).limit(page_size))
        return {"items": [self._present(item) for item in items], "pagination": {"page": page, "page_size": page_size, "total": total}}

    def _get_report(self, report_id):
        report = self.db.reports.find_one({"_id": to_object_id(report_id, "report_id")})
        if not report:
            raise NotFoundError("举报记录不存在")
        return report

    def _present(self, report, detail=False):
        data = serialize_doc(report)
        data["status_text"] = REPORT_STATUS_TEXT.get(report.get("status"), report.get("status", ""))
        data["reason_text"] = report.get("reason_text") or REPORT_REASON_TEXT.get(report.get("reason_type"), "其他")
        data["product"] = {"id": str(report.get("product_id")), "title": report.get("product_title_snapshot", ""), "cover_image": report.get("product_image_snapshot", "")}
        data["seller"] = {"id": str(report.get("seller_id")), "nickname": report.get("seller_nickname_snapshot", "")}
        data["reporter"] = {"id": str(report.get("reporter_id")), "nickname": report.get("reporter_nickname_snapshot", "")}
        if detail:
            data["seller"]["credit_score"] = self.credit.get_score(report["seller_id"])
            data["reporter"]["credit_score"] = self.credit.get_score(report["reporter_id"])
        return data

    def _notify_admin_pending(self, report_id):
        for admin in self.db.users.find({"roles": "admin", "status": "active"}):
            self.db.messages.insert_one({"conversation_id": f"system_{admin['_id']}", "type": "system", "sender_id": admin["_id"], "receiver_id": admin["_id"], "message_type": "system", "system_action": "admin_report_pending", "content": "有新的商品举报待处理", "report_id": report_id, "read_at": None, "created_at": utc_now()})

    def _notify_user(self, receiver_id, action, content, report, sender_id):
        self.db.messages.insert_one({"conversation_id": f"system_{receiver_id}", "type": "system", "sender_id": sender_id, "receiver_id": receiver_id, "message_type": "system", "system_action": action, "content": content, "report_id": report["_id"], "product_id": report.get("product_id"), "read_at": None, "created_at": utc_now()})
