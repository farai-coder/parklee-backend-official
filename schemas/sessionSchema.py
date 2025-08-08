from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class SessionCreate(BaseModel):
    user_id   : UUID
    spot_id   : int
    check_in_time  : datetime
    check_out_time : datetime
