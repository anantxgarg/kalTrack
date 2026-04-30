from pydantic import BaseModel, Field

class LogRequest(BaseModel):
    text: str = Field(..., max_length=200)

class TargetRequest(BaseModel):
    target: int = Field(..., ge=500, le=9999)