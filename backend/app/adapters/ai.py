import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..utils.errors import AppError


class DashScopeTextClient:
    def __init__(self, api_key, base_url, model, timeout_seconds=30):
        self.api_key = api_key
        self.endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate_product_copy(self, payload, action="both"):
        source = {
            "title": (payload.get("title") or "").strip(),
            "description": (payload.get("description") or "").strip(),
            "keywords": (payload.get("keywords") or "").strip(),
            "category": (payload.get("category") or "").strip(),
            "condition": (payload.get("condition") or "").strip(),
            "price": payload.get("price"),
        }
        prompt = (
            "请为校园二手交易商品生成自然、不夸张、像真实同学会写的中文文案。"
            "\n场景：教材书籍、数码配件、宿舍用品、日用品、衣物等校内闲置交易。"
            "\n原则："
            "\n1. 只根据用户给出的信息改写，不虚构品牌、成色、配件、购买时间、保修、包邮或交易承诺。"
            "\n2. 标题要短、顺口、具体，避免“超值好物”“品质优选”“速来抢购”等营销腔。"
            "\n3. 描述要像同学之间转让闲置，口语化但清楚，保留瑕疵、配件、适用场景等重点。"
            "\n4. 信息不足时用中性表达，不要强行补细节。"
            f"\n任务：{action}"
            f"\n现有信息：{json.dumps(source, ensure_ascii=False)}"
            "\n仅返回 JSON 对象，格式："
            '{"title_suggestions":["标题1","标题2","标题3"],"description":"润色后的描述","tags":["标签1","标签2"]}'
            "\n标题每个不超过 24 字；描述 60-180 字；tags 最多 4 个，每个不超过 8 字。"
        )
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是校园二手交易平台的商品文案助手，只输出合法 JSON，不输出 Markdown。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.55,
        }
        request = Request(
            self.endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AppError(50201, f"千问接口调用失败：HTTP {exc.code}", 502, [{"detail": detail[:500]}]) from exc
        except (URLError, TimeoutError) as exc:
            raise AppError(50202, "千问接口连接失败，请稍后重试", 502) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AppError(50203, "千问接口返回格式异常", 502) from exc

        try:
            content = response_data["choices"][0]["message"]["content"]
            result = _parse_json_content(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AppError(50203, "千问接口返回格式异常", 502) from exc
        return _normalize_result(result, source)


def _parse_json_content(content):
    text = str(content or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def _normalize_result(result, source):
    suggestions = []
    for item in result.get("title_suggestions", []):
        title = str(item).strip()[:24]
        if title and title not in suggestions:
            suggestions.append(title)
    if not suggestions and source["title"]:
        suggestions.append(source["title"][:24])

    description = str(result.get("description") or source["description"]).strip()[:300]
    tags = [str(item).strip()[:8] for item in result.get("tags", []) if str(item).strip()][:4]
    return {
        "title": suggestions[0] if suggestions else "",
        "title_suggestions": suggestions[:3],
        "description": description,
        "tags": tags,
    }
