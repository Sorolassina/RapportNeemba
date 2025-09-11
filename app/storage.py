import os, json, re, uuid
from typing import Optional
from fastapi import UploadFile

ROOT = "app/static/uploads"

def _ensure_session(sid: str) -> str:
    path = os.path.join(ROOT, sid)
    os.makedirs(path, exist_ok=True)
    return path

def get_session_dir(sid: str) -> str:
    return _ensure_session(sid)

def _sanitize(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    return name[:120]

def save_upload(sid: str, file: UploadFile) -> str:
    session_dir = _ensure_session(sid)
    fname = file.filename or f"upload-{uuid.uuid4().hex}"
    fname = _sanitize(fname)
    dest = os.path.join(session_dir, fname)
    with open(dest, "wb") as f:
        f.write(file.file.read())
    # return a web path (served under /static)
    web_path = f"/static/uploads/{sid}/{fname}"
    return web_path

def _ctx_path(sid: str) -> str:
    return os.path.join(get_session_dir(sid), "context.json")

def save_context(sid: str, ctx: dict) -> None:
    with open(_ctx_path(sid), "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=2)

def load_context(sid: str) -> dict:
    p = _ctx_path(sid)
    if not os.path.exists(p):
        return {}
    return json.load(open(p, encoding="utf-8"))
