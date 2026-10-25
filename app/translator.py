from typing import Protocol
import httpx
from .config import Settings
from .errors import ServiceError

class Translator(Protocol):
    @property
    def supported_pairs(self) -> set[tuple[str, str]]: ...
    async def translate(self, text: str, source: str, target: str, glossary: dict[str, str]) -> str: ...

class GeminiTranslator:
    # Gemini supports many languages; this service advertises the required assessment pair only.
    supported_pairs = {("en", "hi"), ("hi", "en")}
    def __init__(self, settings: Settings): self.settings = settings
    async def translate(self, text: str, source: str, target: str, glossary: dict[str, str]) -> str:
        if not self.settings.gemini_api_key:
            raise ServiceError(503, "Translation is not configured. Set GEMINI_API_KEY.")
        terms = ", ".join(glossary.keys()) or "None"
        prompt = (f"Translate from {source} to {target}. Preserve meaning and punctuation. "
                  f"Keep these glossary terms exactly as written and untranslated: {terms}. Return only the translation.\n\n{text}")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers={"x-goog-api-key": self.settings.gemini_api_key},
                    json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0}})
        except httpx.RequestError:
            raise ServiceError(503, "Could not connect to the translation service. Please retry shortly.")
        if response.is_error:
            try:
                error=response.json().get("error",{})
                code=error.get("status") or response.status_code
                message=error.get("message") or "request rejected"
            except (ValueError,AttributeError):
                code=response.status_code; message="request rejected"
            raise ServiceError(502,f"Translation provider returned {code}: {message}")
        try: return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError): raise ServiceError(502, "Translation provider returned an invalid response.")

class StubTranslator:
    supported_pairs = {("en", "hi"), ("hi", "en")}
    async def translate(self, text: str, source: str, target: str, glossary: dict[str, str]) -> str:
        return text
