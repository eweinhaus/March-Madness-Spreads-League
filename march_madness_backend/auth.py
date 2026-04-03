import logging
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)


class User(BaseModel):
    uid: str
    email: str
    display_name: str
    league_id: str
    make_picks: bool = True
    admin: bool = False
