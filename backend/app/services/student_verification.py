from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from pymongo import DESCENDING

from ..repositories.users import UserRepository
from ..utils.errors import ConflictError, NotFoundError, ValidationError
from ..utils.images import normalize_image_list, normalize_image_url
from ..utils.serializers import serialize_doc, to_object_id


VERIFICATION_STATUS_TEXT = {
    "none": "未认证",
    "pending": "认证审核中",
    "verified": "已认证",
    "approved": "已认证",
    "rejected": "认证未通过",
}


def utc_now():
    return datetime.now(timezone.utc)


def safe_credit_score(value, default=100):
    if value is None or value == "":
        return default
    try:
        score = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(100, score))


class StudentVerificationService:
    def __init__(self, db):
        self.db = db
        self.users = UserRepository(db)

    def create_application(self, user_id, payload):
        user_object_id = to_object_id(user_id, "user_id")
        user = self.users.find_by_id(user_object_id)
        if not user:
            raise NotFoundError("用户不存在")
        existing = self.db.student_verifications.find_one({"user_id": user_object_id, "status": {"$in": ["pending", "verified", "approved"]}})
        if existing:
            if existing["status"] in {"verified", "approved"}:
                raise ConflictError("你已完成学生认证")
            raise ConflictError("你已提交过认证申请，请等待管理员审核")

        real_name = (payload.get("real_name") or payload.get("name") or "").strip()
        school = (payload.get("school") or payload.get("school_name") or "").strip()
        student_no = (payload.get("student_no") or payload.get("student_id") or "").strip()
        card_image_url = (payload.get("card_image_url") or "").strip()
        student_card_images = payload.get("student_card_images") or []
        if card_image_url:
            student_card_images = [card_image_url]
        if not isinstance(student_card_images, list) or not student_card_images:
            raise ValidationError("参数校验失败", [{"field": "card_image_url", "message": "请上传学生证照片"}])
        if len(student_card_images) > 3:
            raise ValidationError("参数校验失败", [{"field": "card_image_url", "message": "学生证照片最多 3 张"}])
        if not school:
            raise ValidationError("参数校验失败", [{"field": "school", "message": "请填写学校"}])
        if not real_name:
            raise ValidationError("参数校验失败", [{"field": "real_name", "message": "请填写姓名"}])

        profile = self.users.find_profile(user_object_id) or {}
        nickname = profile.get("nickname") or user.get("nickname") or "校园用户"
        now = utc_now()
        doc = {
            "verification_no": f"SV{now.strftime('%Y%m%d%H%M%S')}{uuid4().hex[:6].upper()}",
            "user_id": user_object_id,
            "user_nickname_snapshot": nickname,
            "real_name": real_name,
            "school": school,
            "school_name": school,
            "student_no": student_no,
            "student_id": student_no,
            "card_image_url": normalize_image_url(student_card_images[0]),
            "student_card_images": normalize_image_list(student_card_images),
            "selfie_image": normalize_image_url(payload.get("selfie_image") or ""),
            "status": "pending",
            "reject_reason": "",
            "admin_id": None,
            "admin_note": "",
            "created_at": now,
            "updated_at": now,
            "reviewed_at": None,
        }
        result = self.db.student_verifications.insert_one(doc)
        self.users.update_profile(
            user_object_id,
            {
                "student_verified": False,
                "student_verify_status": "pending",
                "student_verify_reject_reason": "",
                "updated_at": now,
            },
        )
        self._notify_admin_pending(result.inserted_id)
        return self._present(self.db.student_verifications.find_one({"_id": result.inserted_id}), detail=True)

    def get_my_application(self, user_id):
        user_object_id = to_object_id(user_id, "user_id")
        profile = self.users.find_profile(user_object_id) or {}
        application = self.db.student_verifications.find_one({"user_id": user_object_id}, sort=[("created_at", DESCENDING)])
        status = profile.get("student_verify_status") or ("verified" if profile.get("student_verified") else "none")
        return {
            "application": self._present(application, detail=True) if application else None,
            "status": "verified" if status == "approved" else status,
            "status_text": VERIFICATION_STATUS_TEXT.get(status, "未认证"),
            "is_verified": status in {"verified", "approved"},
            "reject_reason": profile.get("student_verify_reject_reason", ""),
        }

    def get_verification_status(self, user_id):
        user_object_id = to_object_id(user_id, "user_id")
        profile = self.users.find_profile(user_object_id) or {}
        status = profile.get("student_verify_status") or ("verified" if profile.get("student_verified") else "none")
        return {"status": "verified" if status == "approved" else status, "status_text": VERIFICATION_STATUS_TEXT.get(status, "未认证"), "is_verified": status in {"verified", "approved"}}

    def list_admin_applications(self, args):
        query = {}
        status = (args.get("status") or "").strip()
        if status:
            if status == "approved":
                status = "verified"
            if status not in {"pending", "verified", "rejected"}:
                raise ValidationError("参数校验失败", [{"field": "status", "message": "审核状态不合法"}])
            query["status"] = status
        data = self._list(query, args)
        data["pending_count"] = self.db.student_verifications.count_documents({"status": "pending"})
        return data

    def get_admin_application(self, application_id):
        return self._present(self._get_application(application_id), detail=True)

    def review_application(self, application_id, admin_user, payload):
        application = self._get_application(application_id)
        if application["status"] != "pending":
            raise ConflictError("当前申请已审核")
        result = (payload.get("result") or payload.get("status") or "").strip()
        if result == "approved":
            result = "verified"
        if result not in {"verified", "rejected"}:
            raise ValidationError("参数校验失败", [{"field": "result", "message": "审核结果不合法"}])
        reject_reason = (payload.get("reject_reason") or payload.get("admin_note") or "").strip()
        if result == "rejected" and not reject_reason:
            raise ValidationError("参数校验失败", [{"field": "reject_reason", "message": "驳回时必须填写原因"}])

        now = utc_now()
        self.db.student_verifications.update_one(
            {"_id": application["_id"]},
            {"$set": {"status": result, "admin_id": admin_user["_id"], "admin_note": reject_reason, "reject_reason": reject_reason, "reviewed_at": now, "updated_at": now}},
        )
        profile_update = {
            "student_verified": result == "verified",
            "student_verify_status": result,
            "student_verify_reject_reason": reject_reason,
            "student_verified_at": now if result == "verified" else None,
            "updated_at": now,
        }
        self.users.update_profile(application["user_id"], profile_update)
        if result == "verified":
            self._notify_user(application["user_id"], "student_verification_verified", "你的学生认证已通过审核", application, admin_user["_id"])
        else:
            self._notify_user(application["user_id"], "student_verification_rejected", f"你的学生认证未通过：{reject_reason}", application, admin_user["_id"])
        return self._present(self._get_application(application_id), detail=True)

    def _list(self, query, args):
        page = max(int(args.get("page", 1)), 1)
        page_size = min(max(int(args.get("page_size", 20)), 1), 50)
        total = self.db.student_verifications.count_documents(query)
        items = list(self.db.student_verifications.find(query).sort("created_at", DESCENDING).skip((page - 1) * page_size).limit(page_size))
        return {"items": [self._present(item) for item in items], "pagination": {"page": page, "page_size": page_size, "total": total}}

    def _get_application(self, application_id):
        application = self.db.student_verifications.find_one({"_id": to_object_id(application_id, "application_id")})
        if not application:
            raise NotFoundError("认证申请不存在")
        return application

    def _present(self, application, detail=False):
        data = serialize_doc(application)
        status = "verified" if application.get("status") == "approved" else application.get("status", "none")
        data["status"] = status
        data["status_text"] = VERIFICATION_STATUS_TEXT.get(status, status)
        data["school"] = application.get("school") or application.get("school_name", "")
        data["school_name"] = data["school"]
        data["student_no"] = application.get("student_no") or application.get("student_id", "")
        data["student_id"] = data["student_no"]
        data["card_image_url"] = application.get("card_image_url") or ((application.get("student_card_images") or [""])[0])
        data["user"] = {"id": str(application.get("user_id")), "nickname": application.get("user_nickname_snapshot", "")}
        if detail:
            profile = self.users.find_profile(application["user_id"]) or {}
            data["user"]["credit_score"] = safe_credit_score(profile.get("credit_score", 100))
        return data

    def _notify_admin_pending(self, application_id):
        for admin in self.db.users.find({"roles": "admin", "status": "active"}):
            self.db.messages.insert_one({"conversation_id": f"system_{admin['_id']}", "type": "system", "sender_id": admin["_id"], "receiver_id": admin["_id"], "message_type": "system", "system_action": "admin_student_verification_pending", "content": "有新的学生认证申请待审核", "verification_id": application_id, "read_at": None, "created_at": utc_now()})

    def _notify_user(self, receiver_id, action, content, application, sender_id):
        self.db.messages.insert_one({"conversation_id": f"system_{receiver_id}", "type": "system", "sender_id": sender_id, "receiver_id": receiver_id, "message_type": "system", "system_action": action, "content": content, "verification_id": application["_id"], "read_at": None, "created_at": utc_now()})
