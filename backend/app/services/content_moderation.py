import os
import json
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bson import ObjectId
from pymongo import DESCENDING

from ..utils.errors import NotFoundError, ValidationError
from ..utils.serializers import serialize_doc, to_object_id


DEFAULT_BANNED_WORDS = [
    {"word": "违禁词", "category": "default", "severity": "high"},
    {"word": "诈骗", "category": "fraud", "severity": "high"},
    {"word": "骗子", "category": "fraud", "severity": "medium"},
    {"word": "骗钱", "category": "fraud", "severity": "high"},
    {"word": "先款", "category": "fraud", "severity": "medium"},
    {"word": "私下转账", "category": "fraud", "severity": "medium"},
    {"word": "微信转账", "category": "fraud", "severity": "medium"},
    {"word": "支付宝转账", "category": "fraud", "severity": "medium"},
    {"word": "假证", "category": "fake_identity", "severity": "high"},
    {"word": "代办学生证", "category": "fake_identity", "severity": "high"},
    {"word": "伪造证件", "category": "fake_identity", "severity": "high"},
    {"word": "网赌", "category": "fraud", "severity": "high"},
    {"word": "博彩", "category": "fraud", "severity": "high"},
    {"word": "毒品", "category": "illegal_product", "severity": "high"},
    {"word": "枪支", "category": "illegal_product", "severity": "high"},
    {"word": "管制刀具", "category": "illegal_product", "severity": "high"},
    {"word": "代写论文", "category": "illegal_product", "severity": "high"},
    {"word": "代考", "category": "illegal_product", "severity": "high"},
    {"word": "辱骂", "category": "harassment", "severity": "medium"},
    {"word": "傻逼", "category": "harassment", "severity": "high"},
    {"word": "傻比", "category": "harassment", "severity": "high"},
    {"word": "煞笔", "category": "harassment", "severity": "high"},
    {"word": "脑残", "category": "harassment", "severity": "medium"},
    {"word": "废物", "category": "harassment", "severity": "medium"},
    {"word": "滚蛋", "category": "harassment", "severity": "medium"},
]

SCENE_TEXT = {
    "product_title": "商品标题",
    "product_desc": "商品描述",
    "chat": "私聊消息",
    "review": "评价内容",
    "report": "举报补充说明",
    "nickname": "用户昵称",
}

RISK_WEIGHT = {"low": 1, "medium": 2, "high": 3}


def utc_now():
    return datetime.now(timezone.utc)


def _normalize_text(value):
    text = str(value or "").lower()
    return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", text))


class ContentModerationService:
    def __init__(self, db, config=None):
        self.db = db
        self.config = config or {}

    def validate_fields(self, user_id, fields):
        result = self.check_fields(fields)
        if result["passed"]:
            return result
        for item in result["matches"]:
            self._record_block(user_id, item)
        raise ValidationError(
            "内容包含违规词，请修改后再提交。",
            [{"field": item["scene"], "message": "内容包含违规词，请修改后再提交。"} for item in result["matches"]],
        )

    def check_fields(self, fields):
        matches = []
        words = self._enabled_words()
        for scene, content in fields.items():
            if content is None or str(content).strip() == "":
                continue
            normalized_content = _normalize_text(content)
            hit_words = []
            hit_categories = []
            risk_level = "low"
            for item in words:
                word = item.get("word", "")
                if not word:
                    continue
                if _normalize_text(word) and _normalize_text(word) in normalized_content:
                    hit_words.append(word)
                    hit_categories.append(item.get("category") or "default")
                    if RISK_WEIGHT.get(item.get("severity"), 1) > RISK_WEIGHT.get(risk_level, 1):
                        risk_level = item.get("severity") or "low"
            ai_result = self.ai_check(content, scene)
            if not ai_result.get("passed", True):
                hit_categories.extend(ai_result.get("hit_categories") or [])
                risk_level = ai_result.get("risk_level") or risk_level
            if hit_words or not ai_result.get("passed", True):
                matches.append(
                    {
                        "scene": scene,
                        "scene_text": SCENE_TEXT.get(scene, scene),
                        "content_snapshot": str(content)[:300],
                        "hit_words": hit_words,
                        "hit_categories": sorted(set(hit_categories)),
                        "risk_level": risk_level,
                        "reason": ai_result.get("reason", ""),
                    }
                )
        return {
            "passed": not matches,
            "risk_level": self._overall_risk(matches),
            "matches": matches,
        }

    def ai_check(self, content, scene):
        enabled = os.getenv("CONTENT_AI_MODERATION_ENABLED", "false").lower() == "true"
        if not enabled:
            return {"passed": True, "risk_level": "low", "reason": "", "hit_categories": []}
        api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        if not api_key:
            return {"passed": True, "risk_level": "low", "reason": "AI内容检测未配置 DASHSCOPE_API_KEY", "hit_categories": []}
        try:
            return self._dashscope_ai_check(content, scene, api_key)
        except Exception as exc:
            return {"passed": True, "risk_level": "low", "reason": f"AI内容检测失败：{exc}", "hit_categories": []}

    def _dashscope_ai_check(self, content, scene, api_key):
        base_url = os.getenv("AI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
        model = (
            os.getenv("CONTENT_AI_MODERATION_MODEL")
            or os.getenv("QWEN_MODEL")
            or os.getenv("AI_MODEL")
            or "qwen-plus"
        ).strip()
        timeout_seconds = int(os.getenv("AI_TIMEOUT_SECONDS", "30") or 30)
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        scene_text = SCENE_TEXT.get(scene, scene)
        prompt = (
            "你是校园二手交易平台的内容安全审核助手。请判断用户输入是否适合发布到平台。\n"
            "重点识别：辱骂骚扰、不当言论、欺诈风险、诱导私下交易、违规商品、虚假身份、恶意交易、隐晦变体和谐音绕过。\n"
            "只返回 JSON，不要返回 Markdown。格式："
            '{"passed":true,"risk_level":"low","reason":"","hit_categories":[]}\n'
            "risk_level 只能是 low、medium、high。hit_categories 从 harassment、fraud、illegal_product、fake_identity、malicious_trade、other 中选择。\n"
            "如果只是正常二手交易描述，应 passed=true。"
            f"\n检测场景：{scene_text}\n待检测内容：{str(content)[:800]}"
        )
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你只输出合法 JSON 对象，不输出解释。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        request = Request(
            endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DashScope HTTP {exc.code}: {detail[:200]}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"DashScope connection failed: {exc}") from exc
        content_text = response_data["choices"][0]["message"]["content"]
        result = _parse_json_content(content_text)
        return _normalize_ai_result(result)

    def list_banned_words(self, args):
        self._ensure_default_words()
        query = {}
        if args.get("category"):
            query["category"] = args.get("category")
        if args.get("enabled") in {"true", "false"}:
            query["enabled"] = args.get("enabled") == "true"
        rows = list(self.db.banned_words.find(query).sort("created_at", DESCENDING))
        return {"items": [serialize_doc(item) for item in rows]}

    def create_banned_word(self, payload):
        word = (payload.get("word") or "").strip()
        if not word:
            raise ValidationError("参数校验失败", [{"field": "word", "message": "请填写违禁词"}])
        doc = {
            "word": word,
            "category": (payload.get("category") or "default").strip(),
            "severity": (payload.get("severity") or "medium").strip(),
            "enabled": bool(payload.get("enabled", True)),
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        result = self.db.banned_words.insert_one(doc)
        return serialize_doc(self.db.banned_words.find_one({"_id": result.inserted_id}))

    def update_banned_word(self, word_id, payload):
        object_id = to_object_id(word_id, "word_id")
        if not self.db.banned_words.find_one({"_id": object_id}):
            raise NotFoundError("违禁词不存在")
        fields = {}
        for key in ["word", "category", "severity"]:
            if key in payload:
                fields[key] = (payload.get(key) or "").strip()
        if "enabled" in payload:
            fields["enabled"] = bool(payload.get("enabled"))
        fields["updated_at"] = utc_now()
        self.db.banned_words.update_one({"_id": object_id}, {"$set": fields})
        return serialize_doc(self.db.banned_words.find_one({"_id": object_id}))

    def delete_banned_word(self, word_id):
        object_id = to_object_id(word_id, "word_id")
        self.db.banned_words.delete_one({"_id": object_id})
        return {"deleted": True, "id": str(object_id)}

    def list_block_records(self, args):
        page = max(int(args.get("page", 1)), 1)
        page_size = min(max(int(args.get("page_size", 20)), 1), 50)
        query = {}
        if args.get("scene"):
            query["scene"] = args.get("scene")
        total = self.db.content_block_records.count_documents(query)
        items = list(
            self.db.content_block_records.find(query)
            .sort("created_at", DESCENDING)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return {"items": [serialize_doc(item) for item in items], "pagination": {"page": page, "page_size": page_size, "total": total}}

    def _enabled_words(self):
        self._ensure_default_words()
        rows = list(self.db.banned_words.find({"enabled": True}))
        merged = {item.get("word"): item for item in DEFAULT_BANNED_WORDS}
        for item in rows:
            merged[item.get("word")] = item
        return list(merged.values())

    def _ensure_default_words(self):
        if self.db.banned_words.count_documents({}) > 0:
            return
        now = utc_now()
        for item in DEFAULT_BANNED_WORDS:
            self.db.banned_words.update_one(
                {"word": item["word"]},
                {
                    "$setOnInsert": {
                        "word": item["word"],
                        "category": item.get("category", "default"),
                        "severity": item.get("severity", "medium"),
                        "enabled": True,
                        "created_at": now,
                        "updated_at": now,
                    }
                },
                upsert=True,
            )

    def _record_block(self, user_id, item):
        self.db.content_block_records.insert_one(
            {
                "user_id": ObjectId(str(user_id)) if user_id else None,
                "scene": item["scene"],
                "content_snapshot": item["content_snapshot"],
                "hit_words": item["hit_words"],
                "hit_categories": item.get("hit_categories", []),
                "risk_level": item["risk_level"],
                "created_at": utc_now(),
            }
        )

    def _overall_risk(self, matches):
        risk = "low"
        for item in matches:
            if RISK_WEIGHT.get(item.get("risk_level"), 1) > RISK_WEIGHT.get(risk, 1):
                risk = item.get("risk_level") or risk
        return risk


def _parse_json_content(content):
    text = str(content or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def _normalize_ai_result(result):
    categories = result.get("hit_categories") or []
    if isinstance(categories, str):
        categories = [categories]
    risk_level = result.get("risk_level") or "low"
    if risk_level not in RISK_WEIGHT:
        risk_level = "medium"
    return {
        "passed": bool(result.get("passed", True)),
        "risk_level": risk_level,
        "reason": str(result.get("reason") or "")[:160],
        "hit_categories": [str(item) for item in categories if str(item).strip()][:5],
    }
