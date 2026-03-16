from .dashboard import router as dashboard_router
from .review import router as review_router
from .files import router as files_router
from .payments import router as payments_router
from .config import router as config_router
from .upload import router as upload_router

__all__ = [
    "dashboard_router",
    "review_router",
    "files_router",
    "payments_router",
    "config_router",
    "upload_router",
]
