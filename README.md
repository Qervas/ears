# Ears 👂

**Learn languages from what you hear.** A self-directed language learning app that builds your vocabulary from real content you consume - radio, videos, podcasts, anything.

## Philosophy

No courses. No teachers. No fixed curriculum. Just you and real content.

1. **Capture** - Record any Swedish audio playing on your computer
2. **Transcribe** - AI converts speech to text
3. **Build Vocabulary** - Words extracted, frequencies tracked
4. **Learn** - AI-powered flashcards, explanations, and conversation practice
5. **Progress** - Your dictionary grows with what you actually hear

## Architecture

```
┌─────────────────────────────────────────┐
│          Tauri Desktop App              │
│  ┌───────────────────────────────────┐  │
│  │       Svelte + TailwindCSS        │  │
│  │   Dashboard │ Vocab │ Learn │ Chat│  │
│  └───────────────────────────────────┘  │
│                   ▼                     │
│  ┌───────────────────────────────────┐  │
│  │          FastAPI Backend          │  │
│  │   Whisper │ LM Studio │ Edge-TTS  │  │
│  └───────────────────────────────────┘  │
│                   ▼                     │
│  ┌───────────────────────────────────┐  │
│  │             SQLite DB             │  │
│  │   Vocab │ Transcripts │ Progress  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Rust (for Tauri desktop build)
- LM Studio (for AI features)

### Backend

```bash
cd backend
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Usage

### 1. Start Backend

```bash
cd backend
python app.py
```

Backend runs on http://localhost:8000

### 2. Start Frontend (Development)

```bash
cd frontend
npm run dev
```

Frontend runs on http://localhost:5173

### 3. Or Run as Desktop App

```bash
cd frontend
npm run tauri dev
```

## Recording Audio

```bash
cd backend
python recorder.py
```

1. Select audio device (use Stereo Mix or similar for system audio)
2. Press Enter to start recording
3. Press Enter to stop
4. Type 'y' to transcribe immediately

## Building Vocabulary

After transcribing:

```bash
cd backend
python vocabulary.py build    # Extract words from transcripts
python vocabulary.py stats    # View statistics
python vocabulary.py top 50   # See most frequent words
```

## Features

- **Dashboard** - Overview of your progress
- **Vocabulary** - Browse all words, filter by status, get AI explanations
- **Learn** - Flashcard-style review with TTS pronunciation
- **AI Chat** - Practice conversation with local LLM
- **Recordings** - Manage and transcribe audio files

## Configuration

Edit `backend/config.py`:

```python
WHISPER_MODEL = "small"      # tiny/base/small/medium
WHISPER_DEVICE = "cpu"       # cpu or cuda
WHISPER_LANGUAGE = "sv"      # Language code
LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
```

## Tech Stack

- **Frontend**: Svelte, TailwindCSS, TypeScript
- **Backend**: FastAPI, Python
- **Desktop**: Tauri (Rust)
- **STT**: faster-whisper
- **TTS**: edge-tts (Microsoft voices)
- **LLM**: LM Studio (local)
- **Database**: SQLite

## License

MIT
