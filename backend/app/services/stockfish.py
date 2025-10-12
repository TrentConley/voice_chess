from __future__ import annotations

import asyncio
import atexit
from typing import Optional

import chess
import chess.engine
from fastapi import HTTPException

from ..core.config import get_settings


class StockfishService:
    def __init__(self, path: Optional[str]) -> None:
        self.path = path or "stockfish"
        self._lock = asyncio.Lock()
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail="Stockfish executable not found") from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Unable to start Stockfish: {exc}") from exc

        self._engine.configure({
            "Skill Level": 5,
            "Hash": 128,
            "Threads": 2
        })
        atexit.register(self._engine.quit)

    async def choose_move(self, board: chess.Board, skill_level: int = 5, think_time: float = 0.1) -> chess.Move:
        async with self._lock:
            # Update skill level for this move
            self._engine.configure({"Skill Level": skill_level})
            board_copy = board.copy(stack=False)
            return await asyncio.to_thread(self._play, board_copy, think_time)

    def _play(self, board: chess.Board, think_time: float) -> chess.Move:
        result = self._engine.play(board, chess.engine.Limit(time=think_time))
        if not result.move:
            raise HTTPException(status_code=500, detail="Stockfish did not return a move")
        return result.move


_service: Optional[StockfishService] = None


def get_stockfish_service() -> StockfishService:
    global _service
    if _service is None:
        settings = get_settings()
        _service = StockfishService(path=settings.stockfish_path)
    return _service
