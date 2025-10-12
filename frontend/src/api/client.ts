import type { SessionState, TurnResponse } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    const message = detail?.detail ?? response.statusText;
    throw new Error(typeof message === "string" ? message : "Request failed");
  }
  return (await response.json()) as T;
}

export async function createSession(skillLevel: number = 5): Promise<SessionState> {
  const response = await fetch(`${API_BASE_URL}/sessions?skill_level=${skillLevel}`, {
    method: "POST",
  });
  return handleResponse<SessionState>(response);
}

export async function updateSkillLevel(sessionId: string, skillLevel: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/skill-level?skill_level=${skillLevel}`, {
    method: "PUT",
  });
  await handleResponse<{skill_level: number}>(response);
}

export async function getSession(sessionId: string): Promise<SessionState> {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`);
  return handleResponse<SessionState>(response);
}

export async function submitTurn(sessionId: string, audio: Blob): Promise<TurnResponse> {
  const formData = new FormData();
  const recording = audio instanceof File ? audio : new File([audio], "turn.webm", { type: audio.type || "audio/webm" });
  formData.append("audio", recording);

  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/turn`, {
    method: "POST",
    body: formData,
  });

  return handleResponse<TurnResponse>(response);
}

export interface StreamUpdate {
  status: 'transcribing' | 'transcribed' | 'interpreting' | 'player_moved' | 'engine_thinking' | 'complete' | 'error';
  transcript?: string;
  move?: { uci: string; san: string };
  user_move?: { uci: string; san: string };
  engine_move?: { uci: string; san: string };
  fen?: string;
  error?: string;
}

export async function submitTurnStream(
  sessionId: string,
  audio: Blob,
  onUpdate: (update: StreamUpdate) => void
): Promise<TurnResponse> {
  const formData = new FormData();
  const recording = audio instanceof File ? audio : new File([audio], "turn.webm", { type: audio.type || "audio/webm" });
  formData.append("audio", recording);

  // Create an AbortController for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 second timeout - snappy!

  try {
    const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/turn-stream`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMessage = errorData?.detail || response.statusText;
      throw new Error(errorMessage);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error("No response body");
    }

    const decoder = new TextDecoder();
    let finalResult: TurnResponse | null = null;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6)) as StreamUpdate;
              onUpdate(data);

              if (data.status === 'complete' && data.fen) {
                finalResult = {
                  transcript: data.transcript!,
                  user_move: data.user_move!,
                  engine_move: data.engine_move!,
                  fen: data.fen,
                  moves: [],
                };
              } else if (data.status === 'error' || data.error) {
                throw new Error(data.error || 'Unknown error');
              }
            } catch (parseError) {
              console.error('Failed to parse SSE line:', line, parseError);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

    if (!finalResult) {
      throw new Error("No final result received from server");
    }

    return finalResult;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error("Request timed out. Please try again with a shorter recording.");
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}
