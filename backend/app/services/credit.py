from datetime import datetime, timezone

from bson import ObjectId

from ..repositories.users import UserRepository
from ..utils.errors import ForbiddenError, NotFoundError, ValidationError
from ..utils.serializers import serialize_doc, to_object_id


CREDIT_LIMIT = 60


def utc_now():
    return datetime.now(timezone.utc)


def clamp_score(value):
    return max(0, min(100, int(value)))


def credit_level(score):
    score = clamp_score(score)
    if score == 100:
        return "信用优秀"
    if score >= 90:
        return "信用良好"
    if score >= 70:
        return "信用一般"
    if score >= 60:
        return "信用偏低"
    return "限制发布"


def default_credit_deduct(reason_type):
    return {
        "fake_info": 10,
        "abnormal_price": 10,
        "prohibited": 20,
        "infringement": 10,
        "spam": 5,
        "harassment": 10,
        "fraud": 20,
        "other": 5,
    }.get(reason_type or "other", 5)


class CreditService:
    def __init__(self, db):
        self.db = db
        self.users = UserRepository(db)

    def get_score(self, user_id):
        user_object_id = user_id if isinstance(user_id, ObjectId) else to_object_id(user_id, "user_id")
        profile = self.users.ensure_profile(user_object_id, {"credit_score": 100, "created_at": utc_now(), "updated_at": utc_now()})
        score = profile.get("credit_score", 100)
        if score is None:
            score = 100
            self.users.update_profile(user_object_id, {"credit_score": score, "updated_at": utc_now()})
        return clamp_score(score)

    def ensure_can_publish(self, user_id):
        if self.get_score(user_id) < CREDIT_LIMIT:
            raise ForbiddenError("信用分低于 60 分，暂时无法发布商品")

    def ensure_can_chat(self, user_id):
        if self.get_score(user_id) < CREDIT_LIMIT:
            raise ForbiddenError("信用分低于 60 分，暂时无法聊天")

    def detail(self, user_id):
        score = self.get_score(user_id)
        return {
            "credit_score": score,
            "credit_level": credit_level(score),
            "can_publish": score >= CREDIT_LIMIT,
            "can_chat": score >= CREDIT_LIMIT,
            "publish_limit_score": CREDIT_LIMIT,
            "need_score_to_publish": max(0, CREDIT_LIMIT - score),
            "rules": credit_rules(),
        }

    def records(self, user_id, args=None):
        args = args or {}
        page = max(int(args.get("page", 1)), 1)
        page_size = min(max(int(args.get("page_size", 20)), 1), 50)
        query = {"user_id": to_object_id(user_id, "user_id")}
        total = self.db.credit_records.count_documents(query)
        items = list(
            self.db.credit_records.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return {"items": [self._present_record(item) for item in items], "pagination": {"page": page, "page_size": page_size, "total": total}}

    def adjust(
        self,
        user_id,
        change_value,
        change_type,
        reason_type,
        reason_text,
        operator_type="system",
        operator_id=None,
        related_report_id=None,
        related_order_id=None,
        related_product_id=None,
    ):
        user_object_id = to_object_id(user_id, "user_id")
        if not self.users.find_by_id(user_object_id):
            raise NotFoundError("用户不存在")
        try:
            delta = int(change_value)
        except (TypeError, ValueError) as exc:
            raise ValidationError("参数校验失败", [{"field": "change_value", "message": "信用分变动必须是整数"}]) from exc
        if delta == 0:
            raise ValidationError("参数校验失败", [{"field": "change_value", "message": "信用分变动不能为 0"}])
        if change_type not in {"deduct", "recover", "admin_adjust"}:
            raise ValidationError("参数校验失败", [{"field": "change_type", "message": "信用分变动类型不合法"}])
        reason_text = (reason_text or "").strip()
        if operator_type == "admin" and not reason_text:
            raise ValidationError("参数校验失败", [{"field": "reason_text", "message": "管理员调整信用分必须填写原因"}])

        before = self.get_score(user_object_id)
        after = clamp_score(before + delta)
        now = utc_now()
        self.db.user_profiles.update_one(
            {"user_id": user_object_id},
            {"$set": {"credit_score": after, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        record = {
            "user_id": user_object_id,
            "change_value": after - before,
            "before_score": before,
            "after_score": after,
            "change_type": change_type,
            "reason_type": reason_type or "other",
            "reason_text": reason_text,
            "related_report_id": to_object_id(related_report_id, "related_report_id") if related_report_id else None,
            "related_order_id": to_object_id(related_order_id, "related_order_id") if related_order_id else None,
            "related_product_id": to_object_id(related_product_id, "related_product_id") if related_product_id else None,
            "operator_type": operator_type,
            "operator_id": to_object_id(operator_id, "operator_id") if operator_id else None,
            "created_at": now,
        }
        result = self.db.credit_records.insert_one(record)
        record = self.db.credit_records.find_one({"_id": result.inserted_id})
        self._notify_credit_change(user_object_id, record)
        return {"credit": self.detail(user_object_id), "record": self._present_record(record)}

    def admin_adjust(self, user_id, payload, admin_user):
        change_value = payload.get("change_value")
        if change_value is None:
            target_score = payload.get("target_score")
            if target_score is None:
                raise ValidationError("参数校验失败", [{"field": "target_score", "message": "请填写调整后的信用分"}])
            try:
                target_score = int(target_score)
            except (TypeError, ValueError) as exc:
                raise ValidationError("参数校验失败", [{"field": "target_score", "message": "信用分必须是 0-100 的整数"}]) from exc
            if target_score < 0 or target_score > 100:
                raise ValidationError("参数校验失败", [{"field": "target_score", "message": "信用分只能是 0-100"}])
            current_score = self.get_score(user_id)
            change_value = target_score - current_score
            if change_value == 0:
                return {"credit": self.detail(user_id), "record": None}
        return self.adjust(
            user_id=user_id,
            change_value=change_value,
            change_type=payload.get("change_type") or "admin_adjust",
            reason_type=payload.get("reason_type") or "admin_adjust",
            reason_text=payload.get("reason_text") or payload.get("reason") or "",
            operator_type="admin",
            operator_id=admin_user["_id"],
            related_report_id=payload.get("related_report_id"),
            related_order_id=payload.get("related_order_id"),
            related_product_id=payload.get("related_product_id"),
        )

    def recover_for_completed_order(self, seller_id, order_id):
        return self.adjust(seller_id, 2, "recover", "completed_order", "正常完成交易且无举报成立，信用分恢复 2 分", related_order_id=order_id)

    def recover_for_good_review(self, seller_id, order_id):
        return self.adjust(seller_id, 5, "recover", "good_review", "收到买家好评，信用分恢复 5 分", related_order_id=order_id)

    def _notify_credit_change(self, user_id, record):
        content = f"信用分变动 {record['change_value']} 分，当前信用分 {record['after_score']} 分"
        self.db.messages.insert_one(
            {
                "conversation_id": f"system_{user_id}",
                "type": "system",
                "sender_id": record.get("operator_id") or user_id,
                "receiver_id": user_id,
                "message_type": "system",
                "system_action": "credit_score_changed",
                "content": content,
                "credit_record_id": record["_id"],
                "read_at": None,
                "created_at": utc_now(),
            }
        )

    def _present_record(self, record):
        data = serialize_doc(record)
        data["change_type_text"] = {"deduct": "扣分", "recover": "恢复", "admin_adjust": "管理员调整"}.get(record.get("change_type"), "信用分变动")
        return data


def credit_rules():
    return {
        "level_rules": [
            {"range": "100", "label": "信用优秀"},
            {"range": "90-99", "label": "信用良好"},
            {"range": "70-89", "label": "信用一般"},
            {"range": "60-69", "label": "信用偏低"},
            {"range": "0-59", "label": "限制发布"},
        ],
        "deduct_rules": [
            {"reason_type": "fake_info", "label": "虚假商品/描述不符", "score": 10},
            {"reason_type": "abnormal_price", "label": "价格异常/诱导交易", "score": 10},
            {"reason_type": "prohibited", "label": "违禁品/违规内容", "score": 20},
            {"reason_type": "infringement", "label": "盗图/侵犯权益", "score": 10},
            {"reason_type": "spam", "label": "垃圾广告/重复发布", "score": 5},
            {"reason_type": "harassment", "label": "辱骂骚扰/不当言论", "score": 10},
            {"reason_type": "fraud", "label": "欺诈风险", "score": 20},
            {"reason_type": "other", "label": "其他违规", "score": 5},
        ],
        "recover_rules": [
            "正常完成交易且无举报成立、无严重售后纠纷，卖家恢复 2 分",
            "收到买家好评，卖家恢复 5 分",
            "连续 7 天无违规可恢复 10 分；当前版本支持管理员手动恢复",
            "管理员手动恢复信用分必须填写原因",
            "用户申诉成功后，管理员可恢复被扣分数",
        ],
        "limits": "信用分低于 60 分时禁止发布商品和聊天；浏览、购买、订单、售后、申诉不受影响。",
        "appeal": "如对扣分或举报处理结果有异议，可联系平台客服或提交申诉，申诉成功后可由管理员恢复信用分。",
    }
