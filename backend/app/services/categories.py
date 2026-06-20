from ..repositories.categories import CategoryRepository
from ..domain.categories import CATEGORY_DEFINITIONS
from ..utils.serializers import serialize_doc


class CategoryService:
    def __init__(self, db):
        self.db = db
        self.categories = CategoryRepository(db)

    def list_categories(self):
        rows = {item.get("code"): item for item in self.categories.list_enabled()}
        items = []
        for definition in CATEGORY_DEFINITIONS:
            row = rows.get(definition["code"]) or definition
            data = serialize_doc(row)
            data["code"] = definition["code"]
            data["name"] = definition["name"]
            data["sort"] = definition["sort"]
            items.append(data)
        return items
