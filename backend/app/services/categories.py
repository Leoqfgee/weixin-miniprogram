from ..repositories.categories import CategoryRepository
from ..utils.serializers import serialize_doc


class CategoryService:
    def __init__(self, db):
        self.categories = CategoryRepository(db)

    def list_categories(self):
        return [serialize_doc(item) for item in self.categories.list_enabled()]
