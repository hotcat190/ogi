from fastapi import APIRouter
from pydantic import BaseModel
import os
from datetime import datetime

router = APIRouter(prefix="/dev", tags=["dev"])

class PerfLogRequest(BaseModel):
    event_type: str
    duration_ms: float
    details: str | None = None
    project_id: str | None = None

@router.post("/perf-log")
async def log_performance(request: PerfLogRequest) -> dict[str, str]:
    os.makedirs("logs", exist_ok=True)
    log_path = "logs/frontend-perf.log"
    with open(log_path, "a") as f:
        proj_str = f" | Project: {request.project_id}" if request.project_id else ""
        details_str = f" | Details: {request.details}" if request.details else ""
        f.write(
            f"[{datetime.now().isoformat()}] {request.event_type.upper()}: "
            f"{request.duration_ms:.2f} ms{proj_str}{details_str}\n"
        )
    return {"status": "logged"}
