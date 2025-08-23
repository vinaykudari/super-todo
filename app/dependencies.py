from functools import lru_cache
from .services.items_service import ItemsService
from .services.logs_service import LogsService


@lru_cache()
def get_items_service() -> ItemsService:
    """Dependency injection for ItemsService."""
    return ItemsService()


@lru_cache()
def get_logs_service() -> LogsService:
    """Dependency injection for LogsService."""
    return LogsService()
