from pydantic import BaseModel

class LogRequest(BaseModel):
    text: str

class TargetRequest(BaseModel):
    target: int