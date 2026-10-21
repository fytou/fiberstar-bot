from .common import router as common_router
from .ingest import router as ingest_router
from .tickets import router as tickets_router
from .status_flow import router as status_flow_router
from .report import router as report_router
from .admin import router as admin_router

__all__ = [
    "common_router",
    "ingest_router",
    "tickets_router",
    "status_flow_router",
    "report_router",
    "admin_router",
]
