"""Explicit local task engine adapters. Optional tools are reported unavailable, never faked."""
from __future__ import annotations
import base64, importlib.util, json, os, shutil, subprocess, tempfile
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

MODELS={"parakeet_local":["nvidia/parakeet-tdt-0.6b-v3"],"whisper_local":["tiny","base","small","medium","large-v3"],"local_ocr":["tesseract"],"deterministic_exif":["exiftool"],"deterministic_image_origin":["pillow-rules-v1"],"local_visual":["llava:latest"]}

def engine_health(engine_id:str)->dict[str,Any]:
    if engine_id=="parakeet_local":
        available=importlib.util.find_spec("nemo") is not None
        return {"status":"healthy" if available else "unavailable","message":"NeMo/Parakeet runtime detected" if available else "Install the optional NeMo ASR runtime to enable Parakeet","models":MODELS[engine_id] if available else []}
    if engine_id=="whisper_local":
        available=importlib.util.find_spec("whisper") is not None or shutil.which("whisper") is not None
        return {"status":"healthy" if available else "unavailable","message":"Local Whisper runtime detected" if available else "Install openai-whisper to enable local Whisper","models":MODELS[engine_id] if available else []}
    if engine_id=="local_ocr":
        available=shutil.which("tesseract") is not None
        return {"status":"healthy" if available else "unavailable","message":"Tesseract detected" if available else "Tesseract executable is not installed","models":MODELS[engine_id] if available else []}
    if engine_id=="deterministic_exif":
        available=shutil.which("exiftool") is not None
        return {"status":"healthy" if available else "unavailable","message":"ExifTool detected" if available else "ExifTool executable is not installed","models":MODELS[engine_id] if available else []}
    if engine_id=="deterministic_image_origin":
        available=importlib.util.find_spec("PIL") is not None
        return {"status":"healthy" if available else "unavailable","message":"Pillow deterministic image-origin rules available" if available else "Pillow is not installed","models":MODELS[engine_id] if available else []}
    if engine_id=="local_visual":
        base_url=os.environ.get("OLLAMA_BASE_URL","http://host.docker.internal:11434").rstrip("/")
        try:
            with urlopen(f"{base_url}/api/tags",timeout=1) as response:
                payload=json.loads(response.read().decode("utf-8"))
            models=[item.get("name") for item in payload.get("models",[]) if item.get("name")]
            return {"status":"healthy","message":"Local Ollama visual endpoint available","models":models}
        except (OSError,URLError,ValueError,json.JSONDecodeError):
            return {"status":"unavailable","message":"Configure a reachable local Ollama visual model to enable selective visual analysis","models":[]}
    return {"status":"unavailable","message":"Unknown local engine","models":[]}

def _path(input_value:Any)->Path:
    value=input_value.get("file_path") if isinstance(input_value,dict) else None
    if not value: raise ValueError("Local media adapters require a server-local file_path")
    path=Path(value).resolve()
    if not path.is_file(): raise ValueError("Input file does not exist")
    return path

def invoke_engine(engine_id:str,task_key:str,input_value:Any,model:str|None,configuration:dict[str,Any])->dict[str,Any]:
    health=engine_health(engine_id)
    if health["status"]!="healthy": raise RuntimeError(health["message"])
    path=_path(input_value)
    if engine_id in ("whisper_local","parakeet_local"):
        normalised,temporary=_normalise_audio(path)
        try:
            if engine_id=="whisper_local": return _whisper(normalised,task_key,model or "base",configuration)
            return _parakeet(normalised,model or MODELS[engine_id][0],configuration)
        finally:
            if temporary: normalised.unlink(missing_ok=True)
    if engine_id=="local_ocr":
        image,temporary=_normalise_image(path)
        try: result=subprocess.run(["tesseract",str(image),"stdout","tsv"],capture_output=True,text=True,timeout=int(configuration.get("timeout_seconds",120)),check=True)
        finally:
            if temporary: image.unlink(missing_ok=True)
        words=[]; lines=result.stdout.splitlines()
        for line in lines[1:]:
            fields=line.split("\t")
            if len(fields)>=12 and fields[11].strip(): words.append({"text":fields[11],"confidence":float(fields[10]) if fields[10] not in ("","-1") else None,"left":int(fields[6]),"top":int(fields[7]),"width":int(fields[8]),"height":int(fields[9])})
        return {"text":" ".join(word["text"] for word in words),"words":words,"engine":engine_id,"model":"tesseract"}
    if engine_id=="deterministic_exif":
        result=subprocess.run(["exiftool","-json","-n",str(path)],capture_output=True,text=True,timeout=30,check=True)
        return {"metadata":json.loads(result.stdout)[0],"engine":engine_id,"model":"exiftool"}
    if engine_id=="deterministic_image_origin":
        return _classify_image_origin(path)
    if engine_id=="local_visual":
        return _ollama_visual(path,task_key,model or MODELS[engine_id][0],configuration)
    raise ValueError(f"No adapter for {engine_id}")

def _classify_image_origin(path:Path)->dict[str,Any]:
    """Return a conservative, evidence-bearing origin candidate.

    This classifier never establishes physical presence. Ambiguous files remain
    ``unknown`` so semantic review can be requested through the same router.
    """
    from PIL import ExifTags, Image
    with Image.open(path) as image:
        width,height=image.size
        image_format=str(image.format or "").upper()
        raw_exif=image.getexif()
        exif={ExifTags.TAGS.get(key,str(key)):value for key,value in raw_exif.items()}
        software=str(exif.get("Software") or image.info.get("Software") or "").strip()
        make=str(exif.get("Make") or "").strip()
        camera_model=str(exif.get("Model") or "").strip()
        captured=str(exif.get("DateTimeOriginal") or exif.get("DateTimeDigitized") or "").strip()
        has_gps=bool(exif.get("GPSInfo"))
    name=path.name.lower();parts={part.lower() for part in path.parts}
    software_lower=software.lower()
    generated_markers=("stable diffusion","midjourney","dall-e","comfyui","automatic1111","firefly")
    screenshot_markers=("screenshot","screen shot","snipping tool","snip & sketch")
    features={
        "width":width,"height":height,"camera_make":make or None,"camera_model":camera_model or None,
        "capture_time_present":bool(captured),"gps_present":has_gps,"editing_software":software or None,
        "screenshot_name_hint":any(value in name for value in screenshot_markers),
        "screenshot_geometry_hint":(width,height) in {(1280,720),(1366,768),(1440,900),(1536,864),(1920,1080),(2560,1440),(3840,2160)} and image_format=="PNG",
        "download_path_hint":bool(parts & {"downloads","download"}),
    }
    if any(marker in software_lower for marker in generated_markers):
        origin,confidence="generated_media",0.95
    elif features["screenshot_name_hint"] or any(marker in software_lower for marker in screenshot_markers) or (features["screenshot_geometry_hint"] and not make and not captured):
        origin,confidence="screenshot",0.92
    elif make and camera_model and captured:
        origin,confidence="camera_origin",0.94
    elif software:
        origin,confidence="edited_media",0.72
    elif features["download_path_hint"]:
        origin,confidence="downloaded_media",0.65
    else:
        origin,confidence="unknown",0.25
    return {"origin":origin,"confidence":confidence,"status":"candidate","features":features,
            "physical_presence_supported":False,"engine":"deterministic_image_origin",
            "model":"pillow-rules-v1","derivation_version":"image-origin-rules-v1"}

def _ollama_visual(path:Path,task_key:str,model:str,configuration:dict[str,Any])->dict[str,Any]:
    if task_key not in {"image.caption","image.landmark_candidate"}:
        raise ValueError(f"local_visual does not support {task_key}")
    prompt=(
        "Describe only visible content; do not infer identity, psychology, or physical presence."
        if task_key=="image.caption" else
        "Return a cautious landmark candidate as JSON with keys place_label, confidence, visual_basis. "
        "A visual match is only a review candidate and never proves physical presence."
    )
    base_url=os.environ.get("OLLAMA_BASE_URL","http://host.docker.internal:11434").rstrip("/")
    body={"model":model,"prompt":prompt,"images":[base64.b64encode(path.read_bytes()).decode("ascii")],
          "stream":False,"format":"json" if task_key=="image.landmark_candidate" else None}
    request=Request(f"{base_url}/api/generate",data=json.dumps(body).encode("utf-8"),headers={"Content-Type":"application/json"},method="POST")
    try:
        with urlopen(request,timeout=int(configuration.get("timeout_seconds",120))) as response:
            payload=json.loads(response.read().decode("utf-8"))
    except (OSError,URLError,json.JSONDecodeError) as exc:
        raise RuntimeError(f"Local visual model invocation failed: {exc}") from exc
    text=str(payload.get("response") or "").strip()
    if task_key=="image.caption":
        return {"text":text,"engine":"local_visual","model":model,"derivation_version":"local-visual-v1"}
    try: candidate=json.loads(text)
    except json.JSONDecodeError: candidate={"place_label":None,"confidence":0.0,"visual_basis":text}
    return {"candidate":candidate,"status":"candidate","physical_presence_supported":False,
            "engine":"local_visual","model":model,"derivation_version":"local-visual-v1"}

def _normalise_audio(path:Path)->tuple[Path,bool]:
    if path.suffix.lower()==".wav": return path,False
    ffmpeg=shutil.which("ffmpeg")
    if not ffmpeg: return path,False
    handle=tempfile.NamedTemporaryFile(suffix=".wav",delete=False);handle.close();target=Path(handle.name)
    subprocess.run([ffmpeg,"-y","-i",str(path),"-ac","1","-ar","16000",str(target)],capture_output=True,timeout=600,check=True)
    return target,True

def _normalise_image(path:Path)->tuple[Path,bool]:
    if path.suffix.lower() not in (".mp4",".mov",".mkv",".webm",".avi"): return path,False
    ffmpeg=shutil.which("ffmpeg")
    if not ffmpeg: raise RuntimeError("FFmpeg is required to OCR a video frame")
    handle=tempfile.NamedTemporaryFile(suffix=".png",delete=False);handle.close();target=Path(handle.name)
    subprocess.run([ffmpeg,"-y","-ss","1","-i",str(path),"-frames:v","1",str(target)],capture_output=True,timeout=120,check=True)
    return target,True

def _whisper(path:Path,task_key:str,model:str,configuration:dict[str,Any])->dict[str,Any]:
    import whisper  # type: ignore
    asr=whisper.load_model(model)
    result=asr.transcribe(str(path),task="translate" if task_key=="speech.translation" else "transcribe",word_timestamps=True,language=configuration.get("language"))
    segments=[]; words=[]
    for segment in result.get("segments",[]):
        segment_words=[{"text":word.get("word","").strip(),"start":word.get("start"),"end":word.get("end"),"probability":word.get("probability")} for word in segment.get("words",[])]
        words.extend(segment_words);segments.append({"id":segment.get("id"),"start":segment.get("start"),"end":segment.get("end"),"text":segment.get("text","").strip(),"words":segment_words,"confidence":{"avg_logprob":segment.get("avg_logprob"),"no_speech_prob":segment.get("no_speech_prob")}})
    return {"text":result.get("text","").strip(),"language":result.get("language"),"segments":segments,"words":words,"confidence":{},"engine":"whisper_local","model":model,"derivation_version":"task2-asr-v1"}

def _parakeet(path:Path,model:str,configuration:dict[str,Any])->dict[str,Any]:
    import nemo.collections.asr as nemo_asr  # type: ignore
    asr=nemo_asr.models.ASRModel.from_pretrained(model_name=model)
    hypotheses=asr.transcribe([str(path)],timestamps=True,return_hypotheses=True);hypothesis=hypotheses[0]
    timestamp=getattr(hypothesis,"timestamp",{}) or {}
    words=[{"text":item.get("word",item.get("char","")),"start":item.get("start"),"end":item.get("end")} for item in timestamp.get("word",[])]
    segments=[{"start":item.get("start"),"end":item.get("end"),"text":item.get("segment","")} for item in timestamp.get("segment",[])]
    return {"text":getattr(hypothesis,"text",str(hypothesis)),"language":configuration.get("language"),"segments":segments,"words":words,"confidence":{},"engine":"parakeet_local","model":model,"derivation_version":"task2-asr-v1"}
