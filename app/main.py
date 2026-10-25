import asyncio, json, logging, tempfile, time, uuid
from pathlib import Path
from typing import Annotated, Literal
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from .audiclabs import AudicLabsClient
from .cache import Cache
from .config import get_settings
from .errors import ServiceError
from .pipeline import Pipeline, language_code
from .translator import GeminiTranslator, StubTranslator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings=get_settings(); client=AudicLabsClient(settings)
translator=StubTranslator() if settings.translator_backend.lower()=="stub" else GeminiTranslator(settings)
pipeline=Pipeline(settings,client,translator,Cache(settings.cache_db))
app=FastAPI(title="AudicLabs Speech Translation API",version="1.0.0",description="Speech translation API with replaceable translation providers.")
jobs: dict[str,dict]={}
lookup_cache: dict[str,tuple[float,object]]={}

class TextRequest(BaseModel):
    text: str = Field(min_length=1, examples=["Good morning. Welcome to the meeting."])
    source_lang: str = Field(examples=["en"])
    target_lang: str = Field(examples=["hi"])
    glossary: dict[str,str] = Field(default_factory=dict, examples=[{"AudicLabs":"AudicLabs"}])

class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, examples=["नमस्ते, आपकी बैठक में स्वागत है।"])
    language: str = Field(examples=["hi-IN"])
    voice: str = Field(description="Voice ID listed by GET /v1/languages. Do not enter spoken text or the placeholder 'string'.")

class AudioResponse(BaseModel):
    audio_url: str = Field(description="Use the returned URL to retrieve the generated MP3.")

class SpeechResponse(BaseModel):
    source_transcript: str
    detected_language: str|None
    translated_text: str
    audio_url: str|None
    timings: dict[str,float]

def _http_error(exc:ServiceError):
    headers={"Retry-After":exc.retry_after} if exc.retry_after else None
    raise HTTPException(status_code=exc.status_code,detail=exc.message,headers=headers)

async def _lookup(endpoint:str):
    cached=lookup_cache.get(endpoint)
    if cached and cached[0]>time.monotonic(): return cached[1]
    data=await client.lookup(endpoint)
    lookup_cache[endpoint]=(time.monotonic()+settings.lookup_cache_seconds,data)
    return data

def _items(data):
    if isinstance(data,list): return data
    if isinstance(data,dict):
        for key in ("data","results","languages","voices","models"):
            if isinstance(data.get(key),list): return data[key]
    return []

async def _catalogs():
    try:
        stt,tts,voices=await asyncio.gather(_lookup("stt/languages"),_lookup("tts/languages"),_lookup("tts/voices"))
        return _items(stt),_items(tts),_items(voices)
    except ServiceError: raise
    except Exception: raise ServiceError(502,"Could not load the language and voice catalogs.")

def _code(item):
    return item if isinstance(item,str) else (item.get("code") or item.get("id") or item.get("language") or item.get("locale") or "")

def _voice_lang(item):
    return language_code(str(item.get("language") or item.get("language_code") or item.get("locale") or ""))

async def _default_voice(target:str):
    _,_,voices=await _catalogs(); wanted=language_code(target)
    for item in voices:
        if isinstance(item,dict) and _voice_lang(item)==wanted: return str(item.get("id") or item.get("voice_id") or "")
    raise ServiceError(422,"No AudicLabs voice is available for the requested target language.")

async def _validate_voice(voice:str,target:str):
    _,_,voices=await _catalogs(); wanted=language_code(target)
    for item in voices:
        if isinstance(item,str):
            if item==voice: return
            continue
        if not isinstance(item,dict): continue
        voice_id=str(item.get("id") or item.get("voice_id") or "")
        if voice_id!=voice: continue
        voice_language=_voice_lang(item)
        if voice_language and voice_language!=wanted:
            raise ServiceError(422,"The selected voice does not match the requested language. Choose a matching voice from GET /v1/languages.")
        return
    raise ServiceError(422,"Unknown voice ID. Choose a voice listed by GET /v1/languages.")

async def _execute(path:Path,source:str,target:str,output:str,glossary:dict,voice:str|None):
    try:
        chosen=voice
        if output in ("audio","both"):
            if not chosen: chosen=await _default_voice(target)
            await _validate_voice(chosen,target)
        return await pipeline.translate_speech(path,source,target,output,glossary,chosen)
    except ServiceError: raise
    finally:
        path.unlink(missing_ok=True)

async def _save_upload(file:UploadFile)->Path:
    suffix=Path(file.filename or "audio.bin").suffix[:12].lower()
    if suffix in {".mp4",".mov",".avi",".mkv"} or (file.content_type or "").lower().startswith("video/"):
        raise ServiceError(415,"This endpoint accepts audio files, not video. Extract the video's audio as WAV or MP3 and upload that file.")
    settings.audio_dir.mkdir(parents=True,exist_ok=True)
    fd,raw=tempfile.mkstemp(prefix="input-",suffix=suffix,dir=settings.audio_dir)
    total=0
    try:
        import os
        with os.fdopen(fd,"wb",closefd=True) as out:
            while chunk:=await file.read(1024*1024):
                total+=len(chunk)
                if total>settings.max_upload_mb*1024*1024: raise ServiceError(413,"The audio file exceeds the configured upload limit.")
                out.write(chunk)
        if total==0: raise ServiceError(422,"The uploaded audio file is empty.")
        return Path(raw)
    except Exception:
        Path(raw).unlink(missing_ok=True); raise

@app.exception_handler(ServiceError)
async def service_error_handler(_,exc:ServiceError):
    headers={"Retry-After":exc.retry_after} if exc.retry_after else None
    return JSONResponse(status_code=exc.status_code,content={"detail":exc.message},headers=headers)

@app.get("/health")
async def health(): return {"status":"ok"}

@app.get("/v1/languages",summary="Supported source and target language pairs")
async def languages():
    try:
        stt,tts,voices=await _catalogs()
        source={language_code(str(_code(item))) for item in stt if _code(item)}
        targets={language_code(str(_code(item))) for item in tts if _code(item)}
        targets|={_voice_lang(item) for item in voices if isinstance(item,dict) and _voice_lang(item)}
        pairs=[{"source_lang":a,"target_lang":b} for a,b in sorted(translator.supported_pairs) if a in source and b in targets]
        return {"pairs":pairs,"stt_languages":stt,"tts_languages":tts,"voices":voices}
    except ServiceError as exc: _http_error(exc)

@app.post("/v1/translate-text")
async def translate_text(body:TextRequest):
    try:
        translated,seconds=await pipeline.translate_text(body.text,body.source_lang,body.target_lang,body.glossary)
        return {"source_text":body.text,"translated_text":translated,"source_lang":body.source_lang,"target_lang":body.target_lang,"timings":{"translation_seconds":seconds}}
    except ServiceError as exc: _http_error(exc)

@app.post("/v1/speak",response_model=AudioResponse,summary="Synthesize speech using an AudicLabs voice")
async def speak(body:SpeakRequest):
    try:
        await _validate_voice(body.voice,body.language)
        filename,_=await pipeline.synthesize(body.text,body.language,body.voice)
        return {"audio_url":f"/v1/audio/{filename}"}
    except ServiceError as exc: _http_error(exc)

@app.get("/v1/audio/{filename}",summary="Download generated MP3 by filename",description="Use only the filename returned in audio_url by /v1/speak or /v1/translate-speech. Do not enter a local Windows file path.",response_class=FileResponse,responses={200:{"content":{"audio/mpeg":{"schema":{"type":"string","format":"binary"}}}}})
async def get_audio(filename:str):
    if Path(filename).name!=filename or not filename.endswith(".mp3"): raise HTTPException(404,"Audio not found. Supply the MP3 filename returned in audio_url.")
    path=settings.audio_dir/filename
    if not path.is_file(): raise HTTPException(404,"Audio not found. First generate speech, then use its audio_url filename.")
    return FileResponse(path,media_type="audio/mpeg",filename=filename)

@app.post("/v1/translate-speech",response_model=SpeechResponse,summary="Translate speech to text and optional translated speech",
          responses={202:{"description":"Async job accepted; poll /v1/jobs/{job_id}."},415:{"description":"Video upload rejected; extract and upload its audio."}})
async def translate_speech(file:Annotated[UploadFile,File(description="Audio file only, up to configured limit. Extract audio from MP4/video files before uploading.")],
    source_lang:Annotated[str,Form()]= "auto", target_lang:Annotated[str,Form()]= "hi", output:Annotated[Literal["text","audio","both"],Form()]= "both",
    glossary_json:Annotated[str,Form()]= "{}", voice:Annotated[str|None,Form(description="Optional voice ID from GET /v1/languages. Leave blank for output=text.")]=None,
    async_mode:Annotated[bool,Query(description="Queue as an async job")]=False):
    try:
        glossary=json.loads(glossary_json)
        if not isinstance(glossary,dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in glossary.items()): raise ValueError()
    except (json.JSONDecodeError,ValueError): raise HTTPException(422,"glossary_json must be a JSON object of strings.")
    try: path=await _save_upload(file)
    except ServiceError as exc: _http_error(exc)
    if async_mode:
        job_id=str(uuid.uuid4()); jobs[job_id]={"status":"queued","result":None,"error":None}
        async def run_job():
            jobs[job_id]["status"]="running"
            try: jobs[job_id]["result"]=await _execute(path,source_lang,target_lang,output,glossary,voice); jobs[job_id]["status"]="completed"
            except ServiceError as exc: jobs[job_id].update(status="failed",error=exc.message)
            except Exception: logging.exception("Unexpected async job failure"); jobs[job_id].update(status="failed",error="The request could not be processed.")
        asyncio.create_task(run_job())
        return JSONResponse(status_code=202,content={"job_id":job_id,"status":"queued","status_url":f"/v1/jobs/{job_id}"})
    try: return await _execute(path,source_lang,target_lang,output,glossary,voice)
    except ServiceError as exc: _http_error(exc)

@app.get("/v1/jobs/{job_id}")
async def get_job(job_id:str):
    if job_id not in jobs: raise HTTPException(404,"Job not found.")
    return {"job_id":job_id,**jobs[job_id]}
