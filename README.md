# Vani 2.0 POC — Stage 1: Application Skeleton and Assessment Generation

## 1. Overview

`vani-2.0-poc` is a dedicated proof-of-concept application built to evaluate and benchmark **Google Cloud Speech-to-Text (STT)** against **Sarvam AI Saaras v4** for voice-based technical assessments.

**Stage 1** establishes the clean application skeleton, candidate skill selection, assessment session creation, question generation workflow (with deterministic fallback bank and optional server-side LLM generator), two-question interview navigation, and automated tests.

---

## 2. Project Structure

```
vani-2.0-poc/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI entry point, CORS, routers, lifespan
│   │   ├── config.py                   # Environment settings via Pydantic Settings
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── skills.py               # SkillsResponse schema
│   │   │   └── assessment.py           # CreateAssessmentRequest, AssessmentResponse, QuestionModel
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── session_store.py        # Isolated in-memory session repository interface & implementation
│   │   │   ├── question_generator.py   # Hybrid question generator, LLM adapter, fallback question bank
│   │   │   ├── tts/                    # Provider-neutral TTS interface (for Stage 2)
│   │   │   │   ├── __init__.py
│   │   │   │   └── base.py
│   │   │   └── stt/                    # Provider-neutral STT interfaces (Google, Sarvam, Compare - Stages 3-4)
│   │   │       ├── __init__.py
│   │   │       └── base.py
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── health.py               # GET /health
│   │       ├── skills.py               # GET /api/skills
│   │       └── assessments.py          # POST /api/assessments, GET /api/assessments/{id}
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                 # TestClient and session cleanup fixtures
│   │   ├── test_health.py              # Health check tests
│   │   ├── test_skills.py              # Skills endpoint tests
│   │   ├── test_assessments.py         # Assessment validation, persistence, and failure tests
│   │   └── test_e2e_flow.py            # End-to-end candidate workflow test
│   ├── requirements.txt
│   ├── .env.example
│   └── pytest.ini
├── frontend/
│   ├── index.html                      # HTML5 entry point
│   ├── package.json                    # Scripts and dependencies (React 18 + Vite)
│   ├── vite.config.js                  # Vite server & API proxy configuration
│   ├── test-check.js                   # Lightweight frontend contract and sanity test
│   ├── .env.example
│   └── src/
│       ├── main.jsx                    # React DOM root mounting
│       ├── App.jsx                     # Top-level screen coordinator (Selection -> Assessment)
│       ├── index.css                   # Vanilla CSS responsive design system
│       ├── api/
│       │   └── client.js               # HTTP client for backend endpoints
│       └── components/
│           ├── SkillSelector.jsx       # 4 selectable skills with multi-select and validation
│           ├── AssessmentView.jsx      # Q1/Q2 navigation stepper without re-generation
│           └── SessionStatusBadge.jsx  # Session ID and generation mode indicator
└── README.md                           # Documentation and setup instructions
```

---

## 3. Prerequisites

- **Python**: 3.10+ (tested on Python 3.13)
- **Node.js**: v18+ (tested on Node v22.18)
- **npm**: v9+ (tested on npm 11.5)

---

## 4. Environment Configuration

### Backend (`backend/.env`)

Copy `backend/.env.example` to `backend/.env`:

```bash
cd backend
cp .env.example .env
```

Key environment variables:

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Host address to bind the FastAPI server |
| `PORT` | `8000` | Port for the FastAPI server |
| `ENVIRONMENT` | `development` | Deployment environment |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Allowed CORS origins for frontend requests |
| `OPENAI_API_KEY` | *(empty)* | Optional. When unset, deterministic fallback mode is used |
| `LLM_MODEL` | `gpt-4o-mini` | Model name if LLM generation is enabled |
| `DEFAULT_STT_MODE` | `google` | STT provider configuration (`google`, `sarvam`, `compare`) |

### Frontend (`frontend/.env`)

Copy `frontend/.env.example` to `frontend/.env`:

```bash
cd frontend
cp .env.example .env
```

In development, Vite proxies requests from `/api` and `/health` to `http://localhost:8000`.

---

## 5. Running Locally

### Step 1: Start Backend

From the project root:

```bash
cd backend

# Create virtual environment (first time only)
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run FastAPI dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend is accessible at:
- API Base: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### Step 2: Start Frontend

In a separate terminal:

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start Vite dev server
npm run dev
```

The frontend will run at `http://localhost:5173`. Open this URL in any modern browser.

---

## 6. Running Tests

### Backend Test Suite (pytest)

```bash
cd backend
.\.venv\Scripts\pytest
```

Output executes 14 unit and integration tests covering:
- Health endpoint status
- Supported skills listing
- Empty skill selection rejection (422)
- Unsupported skill selection rejection (422)
- Invalid question count rejection (422)
- Single-skill assessment creation (201)
- Multi-skill assessment creation (201)
- Question relevance to candidate-selected skills
- Unique assessment ID and unique question IDs
- Session persistence without question re-generation on read
- Session-not-found 404 response
- Multi-session isolation
- Question generation failure behavior (500)
- End-to-end full candidate workflow

### Frontend Checks

```bash
cd frontend
npm test
```

Executes sanity checks verifying component contracts, file structure, and Vite production bundle compilation.

---

## 7. Available API Endpoints

### `GET /health`
Returns service status.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "vani-2.0-poc",
  "stage": "1"
}
```

### `GET /api/skills`
Returns the predefined supported skills.

**Response (200 OK):**
```json
{
  "skills": ["Python", "SQL", "Java", "Machine Learning"]
}
```

### `POST /api/assessments`
Creates an assessment session with exactly 2 questions tailored to the selected skills.

**Request:**
```json
{
  "skills": ["Python", "SQL"],
  "language": "en-IN",
  "question_count": 2,
  "stt_mode": "google"
}
```

**Response (201 Created):**
```json
{
  "assessment_id": "asm_a1b2c3d4e5f6",
  "skills": ["Python", "SQL"],
  "language": "en-IN",
  "question_generation_mode": "fallback",
  "stt_mode": "google",
  "questions": [
    {
      "question_id": "q_78f1a234",
      "text": "When building a high-throughput Python API using an ORM like SQLAlchemy, how do you diagnose and prevent N+1 query bottlenecks, and what database connection pooling configurations would you tune to sustain heavy concurrency?",
      "skills": ["Python", "SQL"]
    },
    {
      "question_id": "q_90e3b567",
      "text": "Given a slow-running SQL query joining multiple multi-million row tables with complex filtering, what specific metrics do you inspect in EXPLAIN ANALYZE, and how do composite indexes help?",
      "skills": ["SQL"]
    }
  ]
}
```

### `GET /api/assessments/{assessment_id}`
Retrieves an existing assessment session. **Does not regenerate questions.**

**Response (200 OK):** Same structure as `POST /api/assessments`.
**Response (404 Not Found):** `{"detail": "Assessment 'asm_...' not found."}`

---

## 8. How Question Generation Works

The question generation architecture uses a **Hybrid Provider Pattern**:

1. **Configured AI Mode (`"ai"`)**:
   - Activated when `OPENAI_API_KEY` is present.
   - Prompts the configured LLM for 2 practical, scenario-based technical questions matching the candidate's selected skills.
   - Questions are strictly validated by `validate_question_list()` before return.
2. **Deterministic Fallback Bank Mode (`"fallback"`)**:
   - Activated when no LLM key is configured, or if the LLM invocation fails.
   - Uses a curated bank of real-world scenario questions covering individual skills (Python, SQL, Java, Machine Learning) and cross-skill combinations (Python + SQL, Python + ML, Java + SQL, Java + ML, SQL + ML).
   - If multiple skills are selected, combination questions are prioritized to maximize coverage within exactly 2 questions.
   - Generates unique question IDs (`q_{uuid}`) and marks `question_generation_mode = "fallback"`.
   - The UI and backend responses explicitly label fallback questions so candidates and interviewers know their origin.

---

## 9. Current Limitations & Architectural Notes

- **In-Memory Session Storage**: Assessment sessions are stored in an in-memory dictionary protected by thread locks (`InMemorySessionStore`). **Sessions will not survive backend restarts.** This is intentional for Stage 1 to avoid database dependencies; a persistent store (e.g. PostgreSQL or Redis) will replace this in future stages using `SessionStoreInterface`.
- **No Active STT / Audio Pipeline**: Stage 1 does not stream audio or call speech providers. Stub interfaces (`TTSProviderInterface`, `GoogleSTTAdapter`, `SarvamSTTAdapter`, `STTBenchmarkOrchestrator`) are defined in `app/services/` in preparation for subsequent stages.

---

## 10. Roadmap: Stages 2–4

- **Stage 2: Audio Capture & Google TTS Playback**
  - Integrate browser microphone recording with `AudioWorklet` (16kHz PCM downsampling).
  - Implement server-side Google Cloud Text-to-Speech adapter to synthesize question audio.
- **Stage 3: Speech-to-Text Provider Integration**
  - Implement `GoogleSTTAdapter` for streaming linear16 transcription via Google Cloud STT API.
  - Implement `SarvamSTTAdapter` for streaming Sarvam AI Saaras v4 transcription with technical keyterm boosting.
- **Stage 4: Benchmark & Comparative Evaluation**
  - Implement dual-stream `compare` mode to run Google STT and Sarvam STT concurrently on candidate audio.
  - Compute Word Error Rate (WER), latency, and technical keyword accuracy metrics.
