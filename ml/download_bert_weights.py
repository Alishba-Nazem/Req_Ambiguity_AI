"""Download bert-base-uncased weights if the Hugging Face hub client stalls."""

from __future__ import annotations

import os
import shutil
import urllib.request
from pathlib import Path

from config import MODEL_NAME, PROJECT_ROOT

CACHE_SNAP = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--google-bert--bert-base-uncased"
    / "snapshots"
    / "86b5e0934494bd15c9632b12f734a8a67f723594"
)
DEST = CACHE_SNAP / "model.safetensors"
URL = "https://huggingface.co/google-bert/bert-base-uncased/resolve/main/model.safetensors"
SEED = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--google-bert--bert-base-uncased"
    / "blobs"
    / "68d45e234eb4a928074dfd868cead0219ab85354cc53d20e772753c6bb9169d3.751b3748.incomplete"
)


def main() -> None:
    CACHE_SNAP.mkdir(parents=True, exist_ok=True)
    if not DEST.exists() and SEED.exists():
        shutil.copyfile(SEED, DEST)
        print("seeded_from_incomplete", DEST.stat().st_size, flush=True)

    existing = DEST.stat().st_size if DEST.exists() else 0
    print("resume_from", existing, flush=True)

    headers = {"User-Agent": "RequirementAmbiguityAI/1.0"}
    if existing:
        headers["Range"] = f"bytes={existing}-"

    req = urllib.request.Request(URL, headers=headers)
    with urllib.request.urlopen(req, timeout=300) as resp:
        print(
            "http_status",
            getattr(resp, "status", None),
            "content_range",
            resp.headers.get("Content-Range"),
            flush=True,
        )
        mode = "ab" if existing and getattr(resp, "status", None) == 206 else "wb"
        n = existing if mode == "ab" else 0
        with DEST.open(mode) as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                n += len(chunk)
                if n % (20 * 1024 * 1024) < 1024 * 1024:
                    print(f"downloaded_mb {n / (1024 * 1024):.1f}", flush=True)

    print("WEIGHTS_OK", DEST, DEST.stat().st_size, flush=True)
    print("project_root", PROJECT_ROOT, flush=True)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
