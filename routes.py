from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from schemas import LogRequest
from services import parse_food_service

router = APIRouter()

@router.get("/")
def index():
    return FileResponse("static/index.html")

@router.head("/")
def head_root():
    return {}

@router.post("/log")
def log_food(req: LogRequest):
    try:
        return parse_food_service(req.text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        print(f"Internal Error: {str(e)}")
        raise HTTPException(status_code=500, detail="An internal service error occurred. Please try again later.")