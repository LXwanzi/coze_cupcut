"""Load account-level content configuration.

The first pluginized account is xiaowanzi_english. Later accounts should add
their own directory under accounts/ and keep the core graph nodes unchanged.
"""

import copy
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


DEFAULT_ACCOUNT_ID = "xiaowanzi_english"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def account_dir(account_id: str) -> Path:
    return repo_root() / "accounts" / account_id


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=16)
def load_account_pack(account_id: str | None = None) -> Dict[str, Any]:
    """Load a complete account plugin pack from accounts/<account_id>/."""
    account_id = account_id or os.getenv("CONTENT_ACCOUNT_ID", DEFAULT_ACCOUNT_ID)
    base = account_dir(account_id)
    return {
        "account_id": account_id,
        "profile": _load_json(base / "account.json", {}),
        "modes": _load_json(base / "modes.json", {}),
        "visual": _load_json(base / "visual.json", {}),
        "quality_rules": _load_json(base / "quality_rules.json", {}),
        "voices": _load_json(base / "voices.json", {}),
        "publish": _load_json(base / "publish.json", {}),
        "output": _load_json(base / "output.json", {}),
        "painpoint_presets": _load_json(base / "painpoint_presets.json", []),
        "scene_collection_presets": _load_json(base / "scene_collection_presets.json", []),
    }


def get_account_pack(account_id: str | None = None) -> Dict[str, Any]:
    """Return a defensive copy so callers can mutate local data safely."""
    return copy.deepcopy(load_account_pack(account_id))
