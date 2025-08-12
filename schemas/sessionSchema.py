from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class SessionCreate(BaseModel):
    user_id   : UUID
    spot_id   : UUID
    check_in_time  : datetime

class SuccessMessage(BaseModel):
    message: str