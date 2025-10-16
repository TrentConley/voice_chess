import { useCallback, useEffect, useMemo, useState, useRef, type MouseEvent } from "react";

import { submitTurnStream, createSession, getSession, updateSkillLevel, type StreamUpdate } from "./api/client";
import { Chessboard } from "./components/Chessboard";
import "./components/Chessboard.css";
import { useAudioRecorder } from "./hooks/useAudioRecorder";
import type { MoveRecord, SessionState } from "./types";

function computeHighlights(moves: MoveRecord[]): string[] {
  if (!moves.length) {
    return [];
  }

  return moves
    .slice(-2)
    .flatMap((move) => {
      const uci = move.uci;
      if (uci.length < 4) {
        return [];
      }
      return [uci.slice(0, 2), uci.slice(2, 4)];
    })
    .filter(Boolean);
}

async function speakMove(sessionId: string, move: string) {
  try {
    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
    const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/tts/${encodeURIComponent(move)}`);
    if (response.ok) {
      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      await audio.play();
      // Clean up object URL after playing
      audio.onended = () => URL.revokeObjectURL(audioUrl);
    }
  } catch (err) {
    console.error("TTS playback failed:", err);
  }
}

export default function App() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMoves, setShowMoves] = useState(true);
  const [showPieces, setShowPieces] = useState(true);
  const [showCoordinates, setShowCoordinates] = useState(true);
  const [skillLevel, setSkillLevel] = useState(5);
  const [gameEnded, setGameEnded] = useState(false);
  const [isMovesCollapsed, setIsMovesCollapsed] = useState(false);
  const { isRecording, start, stop, error: recorderError } = useAudioRecorder();

  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker
        .getRegistrations()
        .then((registrations) => registrations.forEach((registration) => registration.unregister()))
        .catch(() => undefined);
    }
  }, []);

  const startNewGame = useCallback(async () => {
    setIsLoading(true);
    setGameEnded(false);
    setError(null);
    setStatus(null);
    try {
      const created = await createSession(skillLevel);
      setSession(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start session");
    } finally {
      setIsLoading(false);
    }
  }, [skillLevel]);

  useEffect(() => {
    startNewGame();
  }, []);

  useEffect(() => {
    if (recorderError) {
      setError(recorderError);
    }
  }, [recorderError]);

  const highlights = useMemo(() => (session ? computeHighlights(session.moves) : []), [session?.moves]);
  
  // Stabilize FEN to prevent Chessboard re-renders during status changes
  const currentFen = useMemo(() => session?.fen, [session?.fen]);

  const handleStartRecording = useCallback(async () => {
    if (!session?.session_id || isRecording || isSubmitting) {
      return;
    }

    try {
      await start();
      setStatus("Recording... (release to submit)");
      setError(null);
    } catch (err) {
      setStatus(null);
      setError(err instanceof Error ? err.message : "Could not access microphone");
    }
  }, [session, isRecording, isSubmitting, start]);

  const handleStopRecording = useCallback(async () => {
    if (!session?.session_id || !isRecording || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setStatus("Uploading audio...");

    try {
      const blob = await stop();
      if (!blob) {
        throw new Error("No audio captured");
      }

      const handleStreamUpdate = (update: StreamUpdate) => {
        switch (update.status) {
          case 'transcribing':
            setStatus("Transcribing audio...");
            break;
          case 'transcribed':
            setStatus(`Heard: "${update.transcript}"`);
            break;
          case 'interpreting':
            setStatus("Interpreting move with LLM...");
            break;
          case 'player_moved':
            setStatus(`Your move: ${update.move?.san}. Engine is thinking...`);
            break;
          case 'engine_thinking':
            setStatus("Engine is calculating...");
            break;
          case 'complete':
            setStatus(`Complete! Engine replied ${update.engine_move?.san}.`);
            break;
        }
      };

      const turn = await submitTurnStream(session.session_id, blob, handleStreamUpdate);
      
      // Fetch updated session to get full move history
      const updatedSession = await getSession(session.session_id);
      setSession(updatedSession);
      
      setError(null);
      
      // Check for game-ending conditions
      if (turn.engine_move.san === "Checkmate!") {
        setStatus(`Checkmate! You win! Your move: ${turn.user_move.san}`);
        await speakMove(session.session_id, "Checkmate! You win!");
        setGameEnded(true);
      } else if (turn.engine_move.san === "Stalemate") {
        setStatus(`Stalemate! Game drawn. Your move: ${turn.user_move.san}`);
        await speakMove(session.session_id, "Stalemate. Game drawn.");
        setGameEnded(true);
      } else if (turn.engine_move.san.endsWith("#")) {
        setStatus(`Checkmate! Engine wins with ${turn.engine_move.san}`);
        await speakMove(session.session_id, "Checkmate! I win!");
        setGameEnded(true);
      } else if (turn.engine_move.san.includes("Stalemate")) {
        setStatus(`Stalemate! Game drawn. Engine played ${turn.engine_move.san}`);
        await speakMove(session.session_id, "Stalemate. Game drawn.");
        setGameEnded(true);
      } else {
        setStatus(
          `Heard "${turn.transcript}". Interpreted move ${turn.user_move.san}. Engine replied ${turn.engine_move.san}.`
        );
        await speakMove(session.session_id, turn.engine_move.san);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to process move");
      setStatus(null);
    } finally {
      setIsSubmitting(false);
    }
  }, [session, isRecording, isSubmitting, stop]);

  const handleTogglePieces = useCallback((event: MouseEvent<HTMLButtonElement>) => {
    setShowPieces((prev) => !prev);
    event.currentTarget.blur();
  }, []);

  // Prevent Enter key from triggering button clicks
  const handleButtonKeyDown = useCallback((event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
    }
  }, []);

  // Handle keyboard: Hold Enter to record
  // Use refs to avoid recreating handlers on every state change
  const isRecordingRef = useRef(isRecording);
  const isSubmittingRef = useRef(isSubmitting);
  const gameEndedRef = useRef(gameEnded);
  const sessionIdRef = useRef(session?.session_id);

  useEffect(() => {
    isRecordingRef.current = isRecording;
    isSubmittingRef.current = isSubmitting;
    gameEndedRef.current = gameEnded;
    sessionIdRef.current = session?.session_id;
  });

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Enter' && !e.repeat && !isRecordingRef.current && !isSubmittingRef.current && !gameEndedRef.current && sessionIdRef.current) {
        e.preventDefault();
        handleStartRecording();
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'Enter' && isRecordingRef.current && !isSubmittingRef.current) {
        e.preventDefault();
        handleStopRecording();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [handleStartRecording, handleStopRecording]);

  if (isLoading) {
    return <main className="container">Initializing session...</main>;
  }

  if (!session) {
    return <main className="container">Failed to initialize session.</main>;
  }

  return (
    <main className="container">
      <section className="board-section">
        <Chessboard
          fen={currentFen}
          highlights={highlights}
          showCoordinates={showCoordinates}
          showPieces={showPieces}
        />
      </section>

      <section className="control-section">
        <div className="mobile-handle" />
        <h1>Voice Chess</h1>
        <h1>By Trent Conley</h1>

        <p>Hold the button or press Enter, speak your move, then release.</p>
        <div className="tip">
          <span className="tip-icon">💡</span>
          <span>Tip: Say moves like "d 2 to d 4" or "knight g 1 to f 3" for best results</span>
        </div>

        <div className="controls">
          <div className="record-area">
            <div className={`record-button-wrapper ${isSubmitting ? "processing" : ""}`}>
              <button
                className={`btn-record ${isRecording ? "recording" : ""}`}
                onMouseDown={handleStartRecording}
                onMouseUp={handleStopRecording}
                onMouseLeave={handleStopRecording}
                onTouchStart={handleStartRecording}
                onTouchEnd={handleStopRecording}
                disabled={isSubmitting || gameEnded}
                aria-label="Hold to record move"
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                </svg>
              </button>
            </div>
            <div className="record-hint">
              {isRecording ? "Release to submit" : gameEnded ? "Game over" : "Hold or press Enter"}
            </div>
          </div>

          {gameEnded && (
            <button className="btn-restart" onClick={startNewGame}>
              Start New Game
            </button>
          )}

          <div className="skill-level-control">
            <label htmlFor="skill-level">
              <span className="skill-label">Engine Difficulty</span>
              <span className="skill-value">Level {skillLevel}</span>
            </label>
            <input
              id="skill-level"
              type="range"
              min="0"
              max="20"
              value={skillLevel}
              onChange={(e) => setSkillLevel(Number(e.target.value))}
              disabled={isSubmitting || isRecording}
            />
            <div className="skill-markers">
              <span>Beginner</span>
              <span>Expert</span>
            </div>
          </div>

          <div className="status-area">
            {status && <div className="status">{status}</div>}
            {error && <div className="error">{error}</div>}
          </div>

          <div className="toggle-group">
            <button className={`btn-toggle ${showPieces ? "active" : ""}`} onClick={handleTogglePieces} onKeyDown={handleButtonKeyDown}>
              Pieces
            </button>
            <button className={`btn-toggle ${showCoordinates ? "active" : ""}`} onClick={() => setShowCoordinates((prev) => !prev)} onKeyDown={handleButtonKeyDown}>
              Coords
            </button>
            <button className={`btn-toggle ${showMoves ? "active" : ""}`} onClick={() => setShowMoves((prev) => !prev)} onKeyDown={handleButtonKeyDown}>
              History
            </button>
          </div>
        </div>

        {showMoves && (
          <div className={`moves ${isMovesCollapsed ? 'collapsed' : ''}`}>
            <h2 onClick={() => setIsMovesCollapsed(!isMovesCollapsed)}>
              <span>Move History</span>
              <span className="expand-icon">▼</span>
            </h2>
            {!isMovesCollapsed && (
              <>
                {session.moves.length === 0 ? (
                  <p style={{ color: "#a3a3a3", fontSize: "0.875rem" }}>No moves yet.</p>
                ) : (
                  <ol>
                    {session.moves.map((move) => (
                      <li key={`${move.ply}-${move.timestamp}`} className={`move ${move.actor}`}>
                        <strong>{move.actor === "player" ? "You" : "Engine"}</strong>
                        <span>{move.san}</span>
                        {move.actor === "player" && move.transcript ? <em>{move.transcript}</em> : null}
                      </li>
                    ))}
                  </ol>
                )}
              </>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
