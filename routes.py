from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from schemas import LogRequest, TargetRequest
from services import log_food_service, get_today_service, update_target_service, reset_today_service

router = APIRouter()

@router.get("/")
def index():
    return FileResponse("static/index.html")


@router.post("/log")
def log_food(req: LogRequest):
    try:
        return log_food_service(req.text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/today")
def get_today():
    return get_today_service()


@router.put("/target")
def update_target(req: TargetRequest):
    return update_target_service(req.target)


@router.delete("/reset")
def reset_today():
    return reset_today_service()