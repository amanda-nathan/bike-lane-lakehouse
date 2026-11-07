"""Deploy the Bike Lane Explorer Space (a static page, free for everyone; DuckDB runs in the browser). Needs HF_TOKEN in .env.

    uv run --group deploy python huggingface/deploy_space.py

Publish the dataset first (huggingface/publish_dataset.py): the app loads its tables at startup.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")  # HF_TOKEN

SPACE = "AmandaHattaway/bike-lane-explorer"

api = HfApi(token=os.environ["HF_TOKEN"])
api.create_repo(SPACE, repo_type="space", space_sdk="static", exist_ok=True)
api.upload_folder(folder_path=ROOT / "huggingface" / "space", repo_id=SPACE, repo_type="space",
                  commit_message="Update app")
print(f"https://huggingface.co/spaces/{SPACE}")
