"""Load account-level content configuration.

The first pluginized account is xiaowanzi_english. Later accounts should add
their own directory under accounts/ and keep the core graph nodes unchanged.
"""

import copy
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_ACCOUNT_ID = "xiaowanzi_english"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def account_dir(account_id: str) -> Path:
    return repo_root() / "accounts" / account_id


def accounts_root() -> Path:
    return repo_root() / "accounts"


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
        "prompts": _load_json(base / "prompts.json", {}),
        "visual": _load_json(base / "visual.json", {}),
        "quality_rules": _load_json(base / "quality_rules.json", {}),
        "voices": _load_json(base / "voices.json", {}),
        "publish": _load_json(base / "publish.json", {}),
        "output": _load_json(base / "output.json", {}),
        "scenes": _load_json(base / "scenes.json", {}),
        "product_catalog": _load_json(base / "product_catalog.json", {}),
        "script_templates": _load_json(base / "script_templates.json", {}),
        "safety_rules": _load_json(base / "safety_rules.json", {}),
        "painpoint_presets": _load_json(base / "painpoint_presets.json", []),
        "scene_collection_presets": _load_json(base / "scene_collection_presets.json", []),
    }


def get_account_pack(account_id: str | None = None) -> Dict[str, Any]:
    """Return a defensive copy so callers can mutate local data safely."""
    return copy.deepcopy(load_account_pack(account_id))


@lru_cache(maxsize=1)
def list_account_ids() -> List[str]:
    """Return discoverable account plugin ids under accounts/."""
    root = accounts_root()
    if not root.exists():
        return []
    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and (path / "account.json").exists()
    )


def account_exists(account_id: str | None) -> bool:
    return bool(account_id and account_id in list_account_ids())


@lru_cache(maxsize=1)
def account_alias_map() -> Dict[str, str]:
    """Build a normalized alias map from account plugin metadata."""
    aliases: Dict[str, str] = {}
    for account_id in list_account_ids():
        pack = load_account_pack(account_id)
        profile = pack.get("profile") or {}
        candidates = [
            account_id,
            profile.get("account_id", ""),
            profile.get("name", ""),
            *(profile.get("aliases") or []),
        ]
        for candidate in candidates:
            key = str(candidate or "").strip()
            if key:
                aliases[key] = account_id
                aliases[key.lower()] = account_id
    return aliases


def normalize_account_id(value: str | None) -> str:
    account = (value or "").strip()
    if not account:
        return ""
    return account_alias_map().get(account, account_alias_map().get(account.lower(), account))


def resolve_scene_strategy(account_id: str | None, topic: str | None) -> Dict[str, Any]:
    """Resolve account-level scene strategy without hard-coding topics in Python."""
    pack = get_account_pack(account_id)
    scenes = pack.get("scenes") or {}
    scene_groups = scenes.get("scene_groups") or {}
    text = topic or ""

    for scene_id, scene_config in scene_groups.items():
        keywords = scene_config.get("keywords") or []
        if any(str(keyword) and str(keyword) in text for keyword in keywords):
            result = copy.deepcopy(scene_config)
            result["scene_id"] = scene_id
            return result

    default_scene = scenes.get("default_scene")
    if default_scene and default_scene in scene_groups:
        result = copy.deepcopy(scene_groups[default_scene])
        result["scene_id"] = default_scene
        result["is_default"] = True
        return result

    return {}
