import logging
from pathlib import Path
import httpx
from .config import Settings
from .errors import ServiceError, map_upstream_error

log = logging.getLogger("audiclabs")

class AudicLabsClient:
    def __init__(self, settings: Settings): self.settings = settings
    def _headers(self):
        if not self.settings.audiclabs_api_key: raise ServiceError(503, "Speech service is not configured. Set AUDICLABS_API_KEY.")
        return {"Authorization": f"Bearer {self.settings.audiclabs_api_key}"}
    async def _check(self, response: httpx.Response):
        request_id = response.headers.get("X-Request-Id", "unavailable")
        log.info("AudicLabs request status=%s request_id=%s", response.status_code, request_id)
        if response.is_error:
            raise map_upstream_error(response.status_code, response.headers.get("Retry-After"))
    async def transcribe(self, path: Path, language: str | None) -> dict:
        data = {"model": "audic-stt-1"}
        if language and language != "auto": data["language"] = language
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                with path.open("rb") as file:
                    response = await client.post(f"{self.settings.audiclabs_base_url}/stt/transcriptions", headers=self._headers(), data=data,
                        files={"file": (path.name, file, "application/octet-stream")})
        except httpx.RequestError:
            raise ServiceError(503, "Could not connect to the speech service. Please retry shortly.")
        await self._check(response)
        try: return response.json()
        except ValueError: raise ServiceError(502, "Speech service returned invalid transcription data.")
    async def speak(self, text: str, voice: str, language: str) -> bytes:
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(f"{self.settings.audiclabs_base_url}/tts/speech", headers={**self._headers(), "Accept": "audio/mpeg"},
                    json={"model": "audic-tts-1", "input": text, "voice": voice, "language": language, "stream": False})
        except httpx.RequestError:
            raise ServiceError(503, "Could not connect to the speech service. Please retry shortly.")
        await self._check(response)
        return response.content
    async def lookup(self, endpoint: str):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{self.settings.audiclabs_base_url}/{endpoint}", headers=self._headers())
        except httpx.RequestError:
            raise ServiceError(503, "Could not connect to the speech service. Please retry shortly.")
        await self._check(response)
        return response.json()
