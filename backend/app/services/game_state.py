import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
from uuid import uuid4

import chess

from ..models.schemas import MoveRecord, SessionStateResponse


@dataclass
class GameSession:
    session_id: str
    board: chess.Board = field(default_factory=chess.Board)
    moves: List[MoveRecord] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    skill_level: int = 5  # Stockfish skill level (0-20)


class GameStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, GameSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, skill_level: int = 5) -> GameSession:
        async with self._lock:
            session_id = uuid4().hex
            session = GameSession(session_id=session_id, skill_level=skill_level)
            self._sessions[session_id] = session
            return session
    
    def update_skill_level(self, session_id: str, skill_level: int) -> None:
        session = self.get_session(session_id)
        session.skill_level = skill_level

    def get_session(self, session_id: str) -> GameSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def add_move(self, session_id: str, record: MoveRecord) -> None:
        session = self.get_session(session_id)
        session.moves.append(record)

    def to_response(self, session_id: str) -> SessionStateResponse:
        session = self.get_session(session_id)
        return SessionStateResponse(session_id=session.session_id, fen=session.board.fen(), moves=session.moves)


store = GameStore()
