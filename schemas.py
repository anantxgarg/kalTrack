from pydantic import BaseModel

class LogRequest(BaseModel):
    text: str
    device_id: str

class TargetRequest(BaseModel):
    target: int
    device_id: str

class DeviceRequest(BaseModel):
    device_id: str