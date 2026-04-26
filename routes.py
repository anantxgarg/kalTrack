from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from schemas import LogRequest, TargetRequest, DeviceRequest
from services import log_food_service, get_today_service, update_target_service, reset_today_service

router = APIRouter()

@router.get("/")
def index():
    return FileResponse("static/index.html")


@router.post("/log")
def log_food(req: LogRequest):
    try:
        return log_food_service(req.text, req.device_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/today")
def get_today(req: DeviceRequest):
    return get_today_service(req.device_id)


@router.put("/target")
def update_target(req: TargetRequest):
    return update_target_service(req.target, req.device_id)


@router.post("/reset")
def reset_today(req: DeviceRequest):
    return reset_today_service(req.device_id)