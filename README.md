# Voice Chess

A voice-controlled chess application where you speak your moves and play against Stockfish.

## Features

- 🎤 **Voice Input** - Hold Enter or click-and-hold to record your move
- 🤖 **Stockfish Engine** - Play against a configurable AI opponent (difficulty 0-20)
- 🗣️ **Voice Feedback** - Hear the engine's response spoken aloud
- ⚡ **Real-time Updates** - See transcription and move interpretation as they happen
- 🎨 **Modern UI** - Clean, minimalist interface with toggleable board features
- ♟️ **Smart Move Parsing** - Understands various notation formats (UCI, SAN, natural language)

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Groq API key (free tier available)

### Setup

1. Clone the repository

2. Create a `.env` file in the project root:
```bash
GROQ_API_KEY=your_groq_api_key_here
GROQ_TRANSCRIPTION_MODEL=whisper-large-v3-turbo
GROQ_LLM_MODEL=openai/gpt-oss-20b
LOG_LEVEL=INFO
```

3. Start the application:
```bash
docker compose up -d
```

4. Open your browser to [http://localhost:5173](http://localhost:5173)

### Usage

1. **Record a move**: Hold down the microphone button (or press and hold Enter)
2. **Speak your move**: e.g., "pawn to e4", "knight f3", "bishop takes c5"
3. **Release**: The app transcribes, interprets, and plays your move
4. **Listen**: Stockfish responds with its move spoken aloud

### Adjusting Difficulty

Use the **Engine Difficulty** slider to set Stockfish's skill level:
- **0-5**: Beginner
- **6-10**: Intermediate  
- **11-15**: Advanced
- **16-20**: Expert

### Controls

- **Pieces** - Toggle chess piece visibility
- **Coords** - Toggle square coordinates (a1, b2, etc.)
- **History** - Toggle move history panel

## Architecture

- **Backend**: FastAPI (Python) with Stockfish chess engine
- **Frontend**: React + TypeScript with Vite
- **Transcription**: Groq Whisper API (whisper-large-v3-turbo)
- **Move Interpretation**: Groq OpenAI GPT OSS 20B with function calling
- **Chess Engine**: Stockfish

## Development

### View Logs
```bash
docker compose logs -f backend
docker compose logs -f frontend
```

### Rebuild Services
```bash
docker compose build
docker compose up -d --force-recreate
```

### Stop Services
```bash
docker compose down
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | - | Required: Your Groq API key |
| `GROQ_TRANSCRIPTION_MODEL` | `whisper-large-v3-turbo` | Groq transcription model (whisper-large-v3-turbo or whisper-large-v3) |
| `GROQ_LLM_MODEL` | `openai/gpt-oss-20b` | Groq LLM for move interpretation |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Created By

Trent Conley

## License

MIT
