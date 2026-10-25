import hashlib, io, re, time
from pathlib import Path
from pydub import AudioSegment
from .audiclabs import AudicLabsClient
from .cache import Cache
from .config import Settings
from .errors import ServiceError
from .translator import Translator

def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?।])\s+", text.strip()) if s.strip()]

def language_code(value: str) -> str:
    if isinstance(value, dict):
        value = value.get("code") or value.get("language") or value.get("locale") or ""
    normalized = str(value or "").strip().lower().replace("_", "-")
    if normalized.startswith("english"):
        return "en"
    if normalized.startswith("hindi"):
        return "hi"
    code = normalized.split("-", 1)[0]
    return {"eng": "en", "hin": "hi"}.get(code, code)

class Pipeline:
    def __init__(self, settings: Settings, client: AudicLabsClient, translator: Translator, cache: Cache):
        self.settings, self.client, self.translator, self.cache = settings, client, translator, cache
    async def translate_text(self, text: str, source: str, target: str, glossary: dict[str, str]):
        pair = (language_code(source), language_code(target))
        if pair not in self.translator.supported_pairs: raise ServiceError(422, "This language pair is not supported.")
        start = time.perf_counter(); parts=[]
        for sentence in split_sentences(text):
            key = self.cache.key("translation-v1", *pair, sentence, repr(sorted(glossary.items())))
            value = self.cache.get(key)
            if value is None:
                value = await self.translator.translate(sentence, *pair, glossary)
                self.cache.put(key, value)
            parts.append(value)
        return " ".join(parts), round(time.perf_counter()-start, 4)
    async def synthesize(self, text: str, language: str, voice: str):
        self.settings.audio_dir.mkdir(parents=True, exist_ok=True)
        key = self.cache.key("audio-v1", language, voice, text)
        filename = key + ".mp3"; output = self.settings.audio_dir / filename
        start=time.perf_counter()
        if not output.exists():
            sentences=split_sentences(text)
            if not sentences: raise ServiceError(422,"Text is empty after sentence processing.")
            chunks=[await self.client.speak(sentence,voice,language) for sentence in sentences]
            if len(chunks)==1:
                output.write_bytes(chunks[0])
            else:
                try:
                    combined=AudioSegment.empty()
                    for chunk in chunks: combined += AudioSegment.from_file(io.BytesIO(chunk),format="mp3")
                    combined.export(output,format="mp3")
                except FileNotFoundError:
                    raise ServiceError(503,"Joining multiple audio segments requires ffmpeg. Install ffmpeg and retry.")
        return filename, round(time.perf_counter()-start, 4)
    async def translate_speech(self, path: Path, source: str, target: str, output: str, glossary: dict[str,str], voice: str | None):
        st=time.perf_counter(); transcript=await self.client.transcribe(path, None if source=="auto" else source)
        stt=round(time.perf_counter()-st,4)
        text=transcript.get("text")
        if not isinstance(text,str) or not text.strip(): raise ServiceError(422,"Speech service could not find readable speech in this audio.")
        detected_value=transcript.get("language")
        if isinstance(detected_value, dict):
            detected_value=detected_value.get("code") or detected_value.get("language") or detected_value.get("locale")
        detected=str(detected_value).strip() if detected_value else (None if source=="auto" else source)
        if not detected:
            raise ServiceError(422,"Could not detect the source language. Set source_lang to en or hi and retry.")
        translated, translation_time=await self.translate_text(text, detected, target, glossary)
        audio_url=None; tts_time=0
        if output in ("audio","both"):
            if not voice: raise ServiceError(422,"A target-language voice is required for audio output.")
            filename,tts_time=await self.synthesize(translated,target,voice); audio_url=f"/v1/audio/{filename}"
        return {"source_transcript":text,"detected_language":detected,"translated_text":translated,"audio_url":audio_url,
                "timings":{"stt_seconds":stt,"translation_seconds":translation_time,"tts_seconds":tts_time}}
