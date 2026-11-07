"""Create or update the public Hugging Face Space.

Not deployed: as of November 2026, Hugging Face only runs Docker Spaces on free hardware
for PRO subscribers (the create call returns 402 Payment Required). The image builds and
was tested locally; the public version runs on Google Cloud Run instead (cloudrun/).

Uploads the Space files plus the repo files the image needs, and stores the read-only R2
settings as Space secrets. Reads HF_TOKEN and R2_* from .env.

    uv run --group deploy python space/deploy.py
"""

import os
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

SPACE = "AmandaHattaway/bike-lane-lakehouse"
HOST = "amandahattaway-bike-lane-lakehouse.hf.space"
SECRETS = [
    "R2_CATALOG_URI",
    "R2_WAREHOUSE",
    "R2_ENDPOINT",
    "R2_READ_TOKEN",
    "R2_READ_ACCESS_KEY_ID",
    "R2_READ_SECRET_ACCESS_KEY",
]
SKIP = shutil.ignore_patterns("__pycache__", "target", "logs", ".user.yml", ".DS_Store")


def stage(dest: Path) -> None:
    """Lay the files out the way space/Dockerfile expects them: the repo root plus space/."""
    shutil.copy(ROOT / "space" / "Dockerfile", dest / "Dockerfile")
    shutil.copy(ROOT / "space" / "README.md", dest / "README.md")
    shutil.copytree(ROOT / "space", dest / "space", ignore=shutil.ignore_patterns("deploy.py", "Dockerfile", "README.md", "__pycache__"))
    for name in ("pyproject.toml", "uv.lock"):
        shutil.copy(ROOT / name, dest / name)
    for name in ("src", "dbt"):
        shutil.copytree(ROOT / name, dest / name, ignore=SKIP)


def main() -> None:
    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(SPACE, repo_type="space", space_sdk="docker", exist_ok=True)
    for key in SECRETS:
        api.add_space_secret(SPACE, key, os.environ[key])
    api.add_space_variable(SPACE, "MCP_ALLOWED_HOSTS", HOST)

    with tempfile.TemporaryDirectory() as tmp:
        stage(Path(tmp))
        api.upload_folder(
            repo_id=SPACE,
            repo_type="space",
            folder_path=tmp,
            commit_message="Deploy from bike-lane-lakehouse",
            delete_patterns=["*"],  # remove files that are no longer part of the Space
        )
    print(f"Deployed https://huggingface.co/spaces/{SPACE}")
    print(f"MCP endpoint: https://{HOST}/mcp (live once the build finishes)")


if __name__ == "__main__":
    main()
