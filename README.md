# Speech Translation API — Audio In, Translated Text & Speech Out

A Python FastAPI service that converts speech from one language into another, returning translated text and optionally generated speech audio.

The project is designed around AudicLabs Speech-to-Text (STT) and Text-to-Speech (TTS) APIs, with a pluggable translation component.

## Features

- **Speech-to-text:** Transcribe uploaded audio using the AudicLabs STT API.
- **Text translation:** Translate recognized speech or submitted text into a target language.
- **Text-to-speech:** Generate audio from translated text using the AudicLabs TTS API.
- **Multiple output formats:** Request translated text, audio, or both.
- **Language discovery:** Retrieve supported languages and voices from API lookups.
- **Caching:** Reuse eligible results to reduce repeated API calls and credit consumption.
- **Error handling:** Provide meaningful responses for invalid inputs and upstream API errors.
- **Performance measurements:** Track the time taken by individual pipeline stages where implemented.
- **Automated tests:** Test application behaviour without relying on live external API calls.

> **Project status:** This README describes the intended assessment functionality. Verify each feature against the current implementation before claiming it is complete.

## Architecture

### System Overview

This project is a backend-only Speech Translation API built with Python and FastAPI. It accepts audio or text, transcribes speech using the AudicLabs Speech-to-Text (STT) API, translates the text through a pluggable translation provider, and optionally converts the translated text into speech using the AudicLabs Text-to-Speech (TTS) API.

### Architecture Diagram

```text
                 Client / Swagger UI
                         |
                         v
                    FastAPI App
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
   Translate Speech  Translate Text    Speak
          |              |              |
          v              v              |
   AudicLabs STT          |              |
          |              |              |
          +-------+------+              |
                  |                     |
                  v                     |
           Translation Provider         |
                  |                     |
                  v                     |
           Translated Text -------------+
                  |                     |
                  v                     v
             API Response         AudicLabs TTS
                                        |
                                        v
                                  Audio Response

      Supporting Components:
      - Configuration and environment variables
      - Translation/audio cache
      - Error handling and request logging
      - Language/model/voice lookups
      - Background jobs for long-running requests
      - Tests and evaluation samples
```

### Main Components

| Component | Responsibility |
|---|---|
| `app/main.py` | Defines FastAPI routes and API responses. |
| `app/audiclabs.py` | Handles requests to AudicLabs STT and TTS APIs. |
| `app/translator.py` | Provides the translation-provider integration. |
| `app/pipeline.py` | Coordinates transcription, translation, and optional speech generation. |
| `app/cache.py` | Caches reusable translation or audio results. |
| `app/config.py` | Loads configuration and environment variables. |
| `app/errors.py` | Handles API errors and returns consistent error responses. |
| `app/evaluate.py` | Supports translation evaluation. |
| `tests/` | Contains automated tests. |
| `samples/` | Stores sample inputs and outputs. |
| `data/` | Stores runtime data or generated files, depending on configuration. |

### API Workflow

1. The client submits audio or text through a FastAPI endpoint.
2. For audio input, the backend sends the audio to AudicLabs STT to obtain a transcript.
3. The translation provider translates the transcript or submitted text into the target language.
4. If speech output is requested, the backend sends the translated text to AudicLabs TTS.
5. The API returns the transcript, translated text, and—when requested—an audio URL or audio response, according to the endpoint implementation.

### API Endpoints

- `GET /health` — checks service health.
- `GET /v1/languages` — returns supported language information.
- `POST /v1/translate-text` — translates submitted text.
- `POST /v1/speak` — generates speech from text.
- `POST /v1/translate-speech` — transcribes, translates, and optionally generates speech.
- `GET /v1/jobs/{job_id}` — checks the status of an asynchronous job.
- `GET /v1/audio/{audio_id}.mp3` — retrieves generated audio.

### Configuration and Security

API credentials and provider settings are loaded from environment variables or a local `.env` file. The `.env` file must not be committed to version control. Use `.env.example` to document required configuration without including real credentials.

### Testing and Documentation

FastAPI provides interactive API documentation at `/docs`. Automated tests are located in `tests/` and should mock external

### Technology stack

- Python
- FastAPI
- Uvicorn
- HTTPX
- Pydantic Settings
- AudicLabs STT and TTS APIs
- Pytest
- Pydub and FFmpeg for audio processing, where required

## Project Structure

```text
audiclabs-speech-translation/
├── app/
│   ├── main.py
│   ├── audiclabs.py
│   ├── cache.py
│   ├── config.py
│   ├── errors.py
│   ├── pipeline.py
│   ├── translator.py
│   └── evaluate.py
├── tests/
│   └── test_service.py
├── samples/
├── data/
├── .env.example
├── .gitignore
├── Dockerfile
├── requirements.txt
└── README.md
```

The exact contents of `tests/` and `samples/` may differ depending on your implementation.

## Requirements

- Python 3.10 or a compatible version supported by the installed dependencies.
- An AudicLabs API key with the required STT and TTS permissions and available credits.
- A translation provider configured for the selected translator implementation.
- FFmpeg if required for audio conversion or joining.
- Internet access for external API requests.

## Installation

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd audiclabs-speech-translation
```

Replace the placeholder with your repository URL.

### 2. Create a virtual environment

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can run the environment's Python directly using `.venv\Scripts\python.exe`.

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Configuration

Create a local `.env` file using `.env.example` as a template.

Example configuration:

```dotenv
AUDIC_API_KEY=your_audiclabs_api_key
AUDIC_BASE_URL=https://api.audiclabs.com/v1
AUDIC_TIMEOUT_S=120
AUDIC_MAX_RETRIES=3
AUDIC_CONCURRENCY=4

STT_MODEL=audic-stt-1
TTS_MODEL=audic-tts-1

TRANSLATOR=llm
TRANSLATOR_PROVIDER=your_translation_provider
TRANSLATOR_API_KEY=your_translation_api_key
TRANSLATOR_MODEL=your_supported_translation_model

DATA_DIR=./data
MAX_UPLOAD_MB=100
ASYNC_THRESHOLD_MB=10
TTS_CHUNK_CHARS=450
LOOKUP_TTL_S=3600
LOG_LEVEL=INFO
```

These values are examples of configuration names, not a guarantee that every setting is currently implemented. Check `app/config.py` and your translator implementation for the exact supported settings and model identifiers.

**Security requirements:**

- Never commit `.env` or real API keys.
- Keep `.env.example` free of credentials.
- Never expose API keys in frontend JavaScript or a public repository.
- If a key is accidentally exposed, revoke or rotate it.

## Running the API

Start the development server from the repository root:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8081
```

Open the interactive API documentation:

- Swagger UI: http://127.0.0.1:8081/docs
- ReDoc: http://127.0.0.1:8081/redoc
- Health endpoint: http://127.0.0.1:8081/health

The server must be running before these URLs will work.

## API Endpoints

The following endpoints are part of the intended service interface. Confirm their request schemas and behaviour in Swagger UI.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Check service health |
| GET | `/v1/languages` | Retrieve supported languages or language pairs |
| POST | `/v1/translate-text` | Translate submitted text |
| POST | `/v1/speak` | Generate speech from text |
| POST | `/v1/translate-speech` | Transcribe, translate, and optionally generate speech |
| GET | `/v1/jobs/{job_id}` | Check the status of an asynchronous job |
| GET | `/v1/audio/{audio_id}.mp3` | Retrieve generated audio, if supported by the running implementation |

### Text translation example

Example request for `/v1/translate-text`:

```json
{
  "source_lang": "en",
  "target_lang": "hi",
  "text": "Please open the dashboard.",
  "glossary": ["Acme Cloud", "Export"]
}
```

The expected behaviour is to translate the supplied text from English to Hindi while preserving glossary terms. Refer to the live OpenAPI schema for the exact response structure.

### Speech translation

The `/v1/translate-speech` endpoint is intended to accept an audio file, source language or automatic detection, target language, and an output format:

- `text` — return the transcript and translation.
- `audio` — return translated speech audio, along with the relevant transcript and translation fields if supported.
- `both` — return translated text and generated audio.

Check `/docs` for the exact multipart form field names and supported options.

## Running Tests

Run the test suite from the repository root:

```bash
python -m pytest -q
```

For more detailed output:

```bash
python -m pytest tests -v
```

The current development run reported **12 passed**. This confirms those tests passed in that environment; it does not by itself prove that every assessment requirement or live API integration has been verified.

Tests should mock external HTTP calls so they can run without consuming AudicLabs credits.

## Translation Evaluation

The assessment requires translation evaluation for:

- English to Hindi: at least 20 sentences.
- Hindi to English: at least 20 sentences.

Use a documented evaluation command and report BLEU or chrF scores with the corresponding test data and references. Include actual system outputs and note obvious translation errors.

Store reproducible evaluation inputs and outputs in `samples/` or the project's evaluation directory. Report measured scores only after running the evaluation; do not use invented results.

## Error Handling

The application should handle upstream and input errors gracefully:

| Status | Meaning | Expected handling |
|---|---|---|
| 401 / 403 | Authentication or permission issue | Explain that the API credentials or permissions need checking |
| 402 | Insufficient credits | Tell the user that API credits may be exhausted |
| 413 | File too large | Ask the user to upload a smaller file |
| 422 | Invalid or unreadable audio/input | Explain which input needs correcting |
| 429 | Rate limit exceeded | Respect `Retry-After` when supplied |
| 503 | Upstream service unavailable | Retry safely according to the provider's guidance |

Log the `X-Request-Id` associated with upstream requests where available. Avoid returning stack traces or secret values to API clients.

## Docker

A `Dockerfile` is included in the project. Build the image from the repository root:

```bash
docker build -t speech-translation-api .
```

Run the container with your local environment file:

```bash
docker run --rm -p 8081:8081 --env-file .env speech-translation-api
```

Ensure the Dockerfile starts Uvicorn on `0.0.0.0` inside the container and that the configured port matches the published port. Verify this command against the actual Dockerfile before relying on it.

## Frontend

The API can be explored through Swagger UI at `/docs`. A separate browser-based frontend requires its own HTML, CSS, and JavaScript files (or another frontend application).

If a frontend is included in this repository, document its directory and the exact command used to run it here. Keep all external API credentials on the backend.

## Known Limitations

Document the limitations observed in the current implementation, including any that apply to:

- Supported language pairs and voice availability.
- Translation quality and domain-specific terminology.
- Audio formats and maximum upload size.
- Long-running jobs, audio concatenation, and caching.
- Provider availability, API credits, and rate limits.
- Translation evaluation coverage.

Do not claim full support for a language pair until the STT, translation, and TTS components have been verified for that pair.

## Security

- Store credentials in environment variables or a local `.env` file.
- Keep `.env` out of version control.
- Do not put credentials in client-side code, logs, screenshots, or demo recordings.
- Use appropriate timeouts, request validation, and safe error messages.
- Review Git history before making the repository public.

## Assessment Deliverables

Before submitting the project, prepare:

- GitHub repository with reproducible setup instructions.
- `.env.example` containing every required setting without real values.
- Sample inputs and actual outputs.
- Evaluation results for both English-to-Hindi and Hindi-to-English.
- A 1–2 page PDF describing design decisions, measured results, limitations, and next steps.
- A 3–5 minute demo video showing a successful real input, results, and an error case.

## Future Improvements

Possible improvements include:

- A polished, accessible web frontend.
- More translation providers behind the translator interface.
- Improved terminology management and domain-specific evaluation.
- Production authentication, rate limiting, and monitoring.
- Deployment automation and integration testing.

## License

Add an appropriate license if you intend to distribute this repository publicly. Otherwise, specify the access and usage terms required for your assessment submission.
