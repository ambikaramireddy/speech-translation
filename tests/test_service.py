import asyncio
import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from app.cache import Cache
from app.config import Settings
from app.errors import ServiceError, map_upstream_error
from app.main import app
from app.pipeline import Pipeline, split_sentences

class CountingTranslator:
    supported_pairs={("en","hi"),("hi","en")}
    def __init__(self): self.calls=0
    async def translate(self,text,source,target,glossary):
        self.calls+=1
        return f"[{target}] {text}"

class MockSpeech:
    async def transcribe(self,path,language): return {"text":"Hello there. How are you?","language":"en"}
    async def speak(self,text,voice,language): raise AssertionError("text-only path must not invoke TTS")

def test_sentence_split_handles_hindi_and_english_punctuation():
    assert split_sentences("Hello. नमस्ते। Next!") == ["Hello.","नमस्ते।","Next!"]

def test_translation_cache_avoids_duplicate_provider_calls(tmp_path):
    translator=CountingTranslator()
    pipeline=Pipeline(Settings(cache_db=tmp_path/"cache.sqlite3",audio_dir=tmp_path/"audio"),MockSpeech(),translator,Cache(tmp_path/"cache.sqlite3"))
    async def run():
        first=await pipeline.translate_text("Hello. Hello.","en","hi",{})
        second=await pipeline.translate_text("Hello. Hello.","en","hi",{})
        return first,second
    first,second=asyncio.run(run())
    assert first[0]==second[0]
    assert translator.calls==1

def test_single_sentence_speech_saves_mp3_without_ffmpeg(tmp_path):
    class FakeTTS:
        calls=0
        async def speak(self,text,voice,language):
            self.calls+=1
            return b"mock-mp3-data"
    speech=FakeTTS()
    settings=Settings(cache_db=tmp_path/"cache.sqlite3",audio_dir=tmp_path/"audio")
    pipeline=Pipeline(settings,speech,CountingTranslator(),Cache(tmp_path/"cache.sqlite3"))
    filename,_=asyncio.run(pipeline.synthesize("Hello.","en-US","voice-en"))
    assert (settings.audio_dir/filename).read_bytes()==b"mock-mp3-data"
    assert speech.calls==1

def test_unsupported_pair_is_a_clear_client_error(tmp_path):
    pipeline=Pipeline(Settings(cache_db=tmp_path/"cache.sqlite3"),MockSpeech(),CountingTranslator(),Cache(tmp_path/"cache.sqlite3"))
    with pytest.raises(ServiceError,match="language pair"):
        asyncio.run(pipeline.translate_text("Hello","en","fr",{}))

@pytest.mark.parametrize("status,expected",[(401,401),(403,403),(402,402),(413,413),(422,422),(429,429),(503,503)])
def test_upstream_statuses_are_mapped(status,expected):
    assert map_upstream_error(status,"3").status_code==expected
    if status in (429,503): assert map_upstream_error(status,"3").retry_after=="3"

def test_translate_text_endpoint_uses_configured_pipeline(monkeypatch):
    class FakePipeline:
        async def translate_text(self,text,source,target,glossary): return "नमस्ते",0.01
    monkeypatch.setattr("app.main.pipeline",FakePipeline())
    with TestClient(app) as client:
        response=client.post("/v1/translate-text",json={"text":"Hello","source_lang":"en","target_lang":"hi"})
    assert response.status_code==200
    assert response.json()["translated_text"]=="नमस्ते"
