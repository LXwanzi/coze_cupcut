"""Write workflow outputs to a predictable account-configured folder."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from content.account_loader import get_account_pack, repo_root


def write_workflow_output(
    state: Dict[str, Any],
    result: Dict[str, Any],
    account_pack: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    account_pack = account_pack or get_account_pack(state.get("account_id"))
    output_config = account_pack.get("output") or {}
    if not output_config.get("enabled", True):
        return {}

    now = datetime.now()
    content_meta = result.get("content_meta") or state.get("content_meta") or {}
    publish_pack = result.get("publish_pack") or state.get("publish_pack") or {}
    topic = (
        content_meta.get("selected_topic")
        or publish_pack.get("cover_text")
        or state.get("topic")
        or state.get("raw_topic")
        or "topic"
    )
    variables = {
        "account_id": account_pack.get("account_id", "default"),
        "date": now.strftime("%Y%m%d"),
        "time": now.strftime("%H%M%S"),
        "topic_slug": slugify(topic),
    }

    root_dir = Path(output_config.get("root_dir") or "outputs")
    if not root_dir.is_absolute():
        root_dir = repo_root() / root_dir
    output_dir = root_dir / (output_config.get("path_template") or "{account_id}/{date}/{time}_{topic_slug}").format(**variables)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = output_config.get("files") or {}
    written: Dict[str, str] = {}
    payloads = {
        "result": result,
        "segments": result.get("segments") or state.get("segments") or [],
        "publish": publish_pack,
        "review": result.get("review_card") or state.get("review_card") or {},
        "timeline": result.get("timeline_segments") or [],
    }

    for key, payload in payloads.items():
        filename = files.get(key)
        if not filename:
            continue
        path = output_dir / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written[key] = str(path)

    draft_url = result.get("draft_url") or ""
    if files.get("draft_url"):
        path = output_dir / files["draft_url"]
        path.write_text(draft_url, encoding="utf-8")
        written["draft_url"] = str(path)

    if files.get("summary"):
        path = output_dir / files["summary"]
        path.write_text(_build_summary(topic, result), encoding="utf-8")
        written["summary"] = str(path)

    return {
        "output_dir": str(output_dir),
        "output_files": written,
    }


def slugify(value: str) -> str:
    value = (value or "topic").strip().lower()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^\w\u4e00-\u9fff-]", "", value)
    return value[:48] or "topic"


def _build_summary(topic: str, result: Dict[str, Any]) -> str:
    publish_pack = result.get("publish_pack") or {}
    lines = [
        f"# {topic}",
        "",
        f"- success: {result.get('success')}",
        f"- draft_url: {result.get('draft_url') or ''}",
        f"- title: {publish_pack.get('title') or ''}",
        f"- description: {publish_pack.get('description') or ''}",
        "",
        "## Segments",
    ]
    for index, segment in enumerate(result.get("segments") or [], start=1):
        caption = (segment.get("caption") or "").replace("\n", " / ")
        lines.append(f"{index}. {segment.get('scene', '')}: {caption}")
    return "\n".join(lines).strip() + "\n"
