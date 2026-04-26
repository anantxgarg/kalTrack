from pydantic import BaseModel, Field

class LogRequest(BaseModel):
    text: str = Field(..., max_length=200)