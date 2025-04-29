import os
from fastapi import Request
from starlette.responses import RedirectResponse

def clear_uploaded_folder(upload_dir: str) -> None:
    if not os.path.exists(upload_dir):
        return
    for fname in os.listdir(upload_dir):
        fpath = os.path.join(upload_dir, fname)
        if os.path.isfile(fpath):
            os.remove(fpath)

def get_uploaded_images(upload_dir: str):
    if not os.path.exists(upload_dir):
        return []
    return [f for f in os.listdir(upload_dir)
            if (f.lower().endswith('.png') or f.lower().endswith('.jpg')) and f != 'last_debug.png']
