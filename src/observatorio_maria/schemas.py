from pydantic import BaseModel


class Message(BaseModel):
    message: str


class HealthCheck(BaseModel):
    status: str
    database: str
