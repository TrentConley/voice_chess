from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class SessionCreateResponse(BaseModel):
    session_id: str
    fen: str
    moves: list["MoveRecord"]


class MoveRecord(BaseModel):
    ply: int
    actor: Literal["player", "engine"]
    uci: str
    san: str
    transcript: Optional[str] = None
    timestamp: datetime


class MoveResult(BaseModel):
    uci: str
    san: str


class TurnResponse(BaseModel):
    transcript: str
    user_move: MoveResult
    engine_move: MoveResult
    fen: str
    moves: list[MoveRecord]


class SessionStateResponse(BaseModel):
    session_id: str
    fen: str
    moves: list[MoveRecord]


SessionCreateResponse.model_rebuild()
