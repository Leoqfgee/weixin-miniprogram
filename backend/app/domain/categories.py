CATEGORY_DEFINITIONS = [
    {"code": "digital", "name": "数码电子", "sort": 10},
    {"code": "book", "name": "教材书籍", "sort": 20},
    {"code": "clothing", "name": "服饰鞋包", "sort": 30},
    {"code": "home", "name": "生活家居", "sort": 40},
    {"code": "other", "name": "其他", "sort": 99},
]

CATEGORY_NAME_BY_CODE = {item["code"]: item["name"] for item in CATEGORY_DEFINITIONS}
CATEGORY_CODES = set(CATEGORY_NAME_BY_CODE)

LEGACY_CATEGORY_CODE_MAP = {
    "daily": "home",
    "sport": "other",
}

KEYWORD_CATEGORY_RULES = [
    (
        "digital",
        [
            "手机",
            "电脑",
            "耳机",
            "键盘",
            "鼠标",
            "充电宝",
            "平板",
            "相机",
            "数据线",
            "显示器",
            "蓝牙",
            "罗技",
            "机械键盘",
        ],
    ),
    (
        "book",
        [
            "教材",
            "高数",
            "高等数学",
            "英语",
            "考研",
            "四六级",
            "课本",
            "小说",
            "资料",
            "笔记",
            "书籍",
            "图书",
            "同济",
        ],
    ),
    (
        "clothing",
        [
            "衣服",
            "外套",
            "鞋",
            "包",
            "背包",
            "双肩包",
            "帽子",
            "裙子",
            "裤子",
            "卫衣",
        ],
    ),
    (
        "home",
        [
            "台灯",
            "收纳",
            "椅子",
            "桌子",
            "床上用品",
            "水杯",
            "雨伞",
            "镜子",
            "插排",
            "宿舍",
        ],
    ),
]


def normalize_category_code(code):
    value = str(code or "").strip()
    value = LEGACY_CATEGORY_CODE_MAP.get(value, value)
    return value if value in CATEGORY_CODES else ""


def category_name(code):
    return CATEGORY_NAME_BY_CODE.get(normalize_category_code(code), CATEGORY_NAME_BY_CODE["other"])


def classify_category(title="", description=""):
    text = f"{title or ''} {description or ''}".lower()
    for code, keywords in KEYWORD_CATEGORY_RULES:
        if any(keyword.lower() in text for keyword in keywords):
            return code
    return "other"
