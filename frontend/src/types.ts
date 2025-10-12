export type Actor = "player" | "engine";

export interface MoveRecord {
  ply: number;
  actor: Actor;
  uci: string;
  san: string;
  transcript?: string | null;
  timestamp: string;
}

export interface SessionState {
  session_id: string;
  fen: string;
  moves: MoveRecord[];
}

export interface TurnResponse {
  transcript: string;
  user_move: {
    uci: string;
    san: string;
  };
  engine_move: {
    uci: string;
    san: string;
  };
  fen: string;
  moves: MoveRecord[];
}
