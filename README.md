# AudicLabs Speech Translation API

FastAPI backend for speech-to-text, translation, and optional speech synthesis, prepared for assessment AL-PY-02.

## Architecture

`POST /v1/translate-speech` validates an upload, sends it to AudicLabs STT, translates sentence-sized chunks through a swappable translator, and optionally synthesizes each translated chunk through AudicLabs TTS. Synthesized MP3 segments are concatenated in order. `POST /v1/translate-text` and `/v1/speak` expose the smaller building blocks. Translation and TTS results are cached by content hash in SQLite. Long-file requests can run as background jobs and be polled at `/v1/jobs/{job_id}`.

The default translator is a Google Gemini adapter (configurable model) behind a `Translator` protocol. It is selected because it has a simple HTTP API and supports English/Hindi translation; `StubTranslator` makes the service runnable and testable without credentials. The production translator requires `GEMINI_API_KEY`. Swap it by implementing the protocol in `app/translator.py`.

## Setup

Python 3.11+ and ffmpeg are needed. Install dependencies and configure secrets:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `AUDICLABS_API_KEY` and `GEMINI_API_KEY` in `.env`. Never commit `.env`. For local API exploration without external calls, set `TRANSLATOR_BACKEND=stub`; STT/TTS still require AudicLabs credentials.

## Run

```powershell
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`. See `POST /v1/translate-speech` for multipart fields `file`, `source_lang` (`auto` by default), `target_lang`, and `output` (`text`, `audio`, or `both`). Audio responses contain a relative `audio_url`; retrieve it from `GET /v1/audio/{filename}`. Use `?async_mode=true` for job submission and poll the returned job ID.

## Configuration

See `.env.example`. Runtime language and voice catalogs are fetched from AudicLabs lookup endpoints and cached briefly; the service does not maintain a hardcoded list of API voices. `GET /v1/languages` intersects those catalogs with the translator's configured supported pairs.

## Tests

```powershell
pytest
```

Tests mock external APIs and do not spend credits. External quality evaluation can be run with `python -m app.evaluate`; it scores the included 20+ bilingual sentence pairs using corpus BLEU and chrF. This is a reproducible smoke benchmark, not a claim of independent human evaluation.

## Assumptions and limitations

- Gemini is the initial translator; model quality, latency, and cost depend on the configured account/model. Replace it with a self-hosted IndicTrans2 adapter when local model operation is preferred.
- AudicLabs lookup response shapes can vary; adapters tolerate common `data`/`results` wrappers. Confirm exact voice/language fields against the issued API documentation and credentials.
- MP3 joining uses ffmpeg through pydub. Long files are processed in memory by STT, so production deployments should stream uploads and use durable job storage.
- Background jobs and cache use local SQLite/filesystem and are suitable for a single instance. Use shared storage and a queue for multi-instance deployment.
- The 20+ evaluation sentences are included as a starter benchmark and are not an official assessment corpus. The documented command measures the configured translator and prints scores; no score is claimed until run with credentials.
- API calls log `X-Request-Id`; errors are mapped to concise client-safe messages, including rate-limit retry guidance.

## Assessment deliverables still requiring candidate action

Run the quality command with the provided credentials, review outputs, record a 3–5 minute demo on real input, and write the final 1–2 page submission PDF with measured results. Do not publish the assessment document, credentials, or sample audio without permission.
