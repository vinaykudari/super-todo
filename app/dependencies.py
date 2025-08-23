from functools import lru_cache
from .services.items_service import ItemsService


@lru_cache()
def get_items_service() -> ItemsService:
    """Dependency injection for ItemsService."""
    return ItemsService()
