import json

from app.adapters.ai import DashScopeTextClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def test_dashscope_product_copy_parses_structured_result(monkeypatch):
    response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "title_suggestions": ["九成新蓝牙耳机", "校园自提蓝牙耳机", "闲置蓝牙耳机转让"],
                            "description": "九成新蓝牙耳机，功能正常，具体配件与瑕疵请当面确认。",
                            "tags": ["蓝牙耳机", "校内自提"],
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ]
    }
    monkeypatch.setattr("app.adapters.ai.urlopen", lambda request, timeout: FakeResponse(response))

    result = DashScopeTextClient(
        api_key="test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
    ).generate_product_copy({"title": "蓝牙耳机", "description": "九成新"}, "both")

    assert len(result["title_suggestions"]) == 3
    assert result["title"] == "九成新蓝牙耳机"
    assert "功能正常" in result["description"]


def test_dashscope_product_copy_accepts_json_code_fence(monkeypatch):
    content = '```json\n{"title_suggestions":["教材转让"],"description":"教材有少量笔记。","tags":[]}\n```'
    monkeypatch.setattr(
        "app.adapters.ai.urlopen",
        lambda request, timeout: FakeResponse({"choices": [{"message": {"content": content}}]}),
    )

    result = DashScopeTextClient("test-key", "https://example.com/v1", "qwen-plus").generate_product_copy(
        {"title": "教材"},
        "description",
    )

    assert result["title"] == "教材转让"
    assert result["description"] == "教材有少量笔记。"
