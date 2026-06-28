"""Metaphysics account script generation."""

import hashlib
from typing import Any, Dict, List


MONEY_KEYWORDS = ["钱留不住", "漏财", "守财", "花钱", "存不住钱", "财"]


def is_metaphysics_account(account_pack: Dict[str, Any]) -> bool:
    profile = account_pack.get("profile") or {}
    return (
        account_pack.get("account_id") == "metaphysics"
        or profile.get("account_id") == "metaphysics"
        or profile.get("domain") == "metaphysics_lifestyle"
    )


def build_metaphysics_plan(
    state: Dict[str, Any],
    account_pack: Dict[str, Any],
) -> Dict[str, Any]:
    raw_topic = state.get("raw_topic") or state.get("topic") or "最近状态不太稳"
    mode, topic = _extract_mode_and_topic(raw_topic, account_pack)
    scene = state.get("scene") or _detect_scene(topic, account_pack)
    product = _select_product(topic, scene, account_pack)
    voice_profile = _voice_profile(mode, account_pack)
    brief = _build_brief(topic, mode, scene, product)
    segments = _build_segments(brief)
    segments = [_apply_visual_metadata(seg, account_pack) for seg in segments]
    duration_seconds = sum(seg.get("duration", 4.0) for seg in segments)
    content_meta = {
        "account_id": account_pack.get("account_id", "metaphysics"),
        "selected_topic": brief["topic"],
        "scene": scene,
        "sub_scene": scene,
        "duration_seconds": duration_seconds,
        "target_duration_seconds": state.get("duration_seconds", 28),
        "sentence_count": len(segments),
        "format": "metaphysics_product_seed",
        "content_mode": mode,
        "voice_profile": voice_profile,
        "product": product,
        "topic_id": _topic_id(topic, scene),
        "safety_note": "玄学内容仅作传统寓意和生活仪式感参考，不承诺结果。",
    }
    return {
        "segments": segments,
        "content_meta": content_meta,
        "publish_pack": _build_publish_pack(brief, mode, account_pack),
        "review_card": {
            "today_expressions": [],
            "answer_levels": [],
            "quick_review": brief["soft_claim"],
            "product": product,
        },
        "episode_info": {
            "season_name": brief["topic"],
            "review": "",
            "preview": "下次继续聊适合新手的开运小物。",
        },
        "topic_id": content_meta["topic_id"],
        "video_plan": {
            "canvas": {
                "width": state.get("canvas_width", 1080),
                "height": state.get("canvas_height", 1920),
            },
            "duration": int(duration_seconds * 1_000_000),
        },
    }


def _extract_mode_and_topic(raw_topic: str, account_pack: Dict[str, Any]) -> tuple[str, str]:
    modes = (account_pack.get("modes") or {}).get("mode_aliases") or {}
    text = (raw_topic or "").strip()
    for separator in ("：", ":"):
        if separator in text:
            prefix, topic = text.split(separator, 1)
            prefix = prefix.strip()
            if prefix in modes:
                return modes[prefix], topic.strip()
    if any(keyword in text for keyword in MONEY_KEYWORDS):
        return "painpoint_conversion", text
    return "scene_product_seed", text


def _detect_scene(topic: str, account_pack: Dict[str, Any]) -> str:
    for scene, keywords in (account_pack.get("modes") or {}).get("scene_map") or []:
        if any(keyword in topic for keyword in keywords):
            return scene
    return "entryway"


def _select_product(topic: str, scene: str, account_pack: Dict[str, Any]) -> Dict[str, Any]:
    products = (account_pack.get("product_catalog") or {}).get("products") or []
    for product in products:
        product_scenes = product.get("scenes") or []
        if any(item in topic for item in product_scenes) or scene in _scene_aliases(product_scenes):
            return product
    if any(keyword in topic for keyword in MONEY_KEYWORDS):
        for product in products:
            if product.get("name") in ["五帝钱", "小貔貅摆件", "黄水晶小摆件"]:
                return product
    return products[0] if products else {
        "name": "开运小物",
        "meaning": "给自己一个稳定提醒",
        "scenes": ["玄关"],
    }


def _scene_aliases(product_scenes: List[str]) -> List[str]:
    aliases = {
        "玄关": "entryway",
        "入户": "entryway",
        "钱包": "wallet",
        "办公桌": "desk",
        "书桌": "desk",
        "卧室": "bedroom",
        "车内": "car",
        "随身佩戴": "wearable",
    }
    return [aliases[item] for item in product_scenes if item in aliases]


def _voice_profile(mode: str, account_pack: Dict[str, Any]) -> Dict[str, Any]:
    voices = (account_pack.get("modes") or {}).get("voice_profiles") or {}
    return voices.get(mode) or voices.get("default") or {"voice": "gentle", "speed": 1.03}


def _build_brief(topic: str, mode: str, scene: str, product: Dict[str, Any]) -> Dict[str, Any]:
    product_name = product.get("name", "开运小物")
    meaning = product.get("meaning", "给自己一个稳定提醒")
    clean_topic = topic.replace("玄学方向", "").strip() or topic
    pain_point = clean_topic if clean_topic.startswith(("最近", "总觉得", "老是")) else f"最近总觉得{clean_topic}"
    hook = f"{clean_topic}，先别急着焦虑。"
    if any(keyword in clean_topic for keyword in MONEY_KEYWORDS):
        product_reason = f"{product_name}更适合做一个守财感提醒，寓意是{meaning}。"
        placement = "可以放在钱包、玄关或每天会看到的位置，重点是提醒自己少冲动消费。"
    else:
        product_reason = f"{product_name}适合用来增加一点稳定的仪式感，寓意是{meaning}。"
        placement = "放在你每天会经过或会看到的位置就好，保持干净、不杂乱。"
    return {
        "topic": clean_topic,
        "mode": mode,
        "scene": scene,
        "hook": hook,
        "pain_point": f"你{pain_point}",
        "traditional_view": "传统说法里，状态不稳时先看空间和随身物件的秩序感。",
        "real_life_view": "现实一点说，它更像给自己一个慢下来、少乱花的提醒。",
        "product_angle": product_name,
        "product_reason": product_reason,
        "placement": placement,
        "soft_claim": "玄学小物只做寓意和提醒，不保证结果，关键还是自己的节奏。",
        "interaction": "你最近是钱留不住，还是心里总觉得不踏实？",
        "title": f"【{clean_topic[:10]}】想稳一点，可以先看这个",
    }


def _build_segments(brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "scene": "痛点钩子",
            "caption": f"{brief['hook']}\n适合先收藏慢慢看",
            "tts": f"{brief['hook']}适合先收藏慢慢看。",
            "image_prompt": _image_prompt(brief, "opening"),
            "duration": 3.2,
        },
        {
            "scene": "场景代入",
            "caption": brief["pain_point"],
            "tts": brief["pain_point"],
            "image_prompt": _image_prompt(brief, "life scene"),
            "duration": 4.0,
        },
        {
            "scene": "传统说法",
            "caption": brief["traditional_view"],
            "tts": brief["traditional_view"],
            "image_prompt": _image_prompt(brief, "traditional view"),
            "duration": 4.2,
        },
        {
            "scene": "产品建议",
            "caption": f"{brief['product_angle']}\n{brief['product_reason']}",
            "tts": f"可以看看{brief['product_reason']}",
            "image_prompt": _image_prompt(brief, "product close up"),
            "keywords": [brief["product_angle"]],
            "duration": 4.8,
        },
        {
            "scene": "摆放建议",
            "caption": brief["placement"],
            "tts": brief["placement"],
            "image_prompt": _image_prompt(brief, "placement tips"),
            "duration": 4.2,
        },
        {
            "scene": "自然问句",
            "caption": brief["interaction"],
            "tts": brief["interaction"],
            "image_prompt": _image_prompt(brief, "soft interaction"),
            "duration": 3.2,
        },
    ]


def _image_prompt(brief: Dict[str, Any], moment: str) -> str:
    return (
        f"{brief['topic']}, {brief['product_angle']}, metaphysics lifestyle short video, "
        f"moment: {moment}, product-focused still life, no text, no speech bubbles"
    )


def _apply_visual_metadata(segment: Dict[str, Any], account_pack: Dict[str, Any]) -> Dict[str, Any]:
    visual = account_pack.get("visual") or {}
    updated = dict(segment)
    animation = visual.get("animation_defaults") or {}
    if animation:
        updated["animation"] = dict(animation)
    highlight = visual.get("caption_highlight") or {}
    keywords = updated.get("keywords") or []
    if highlight.get("enabled") and keywords:
        updated["caption_highlight"] = {
            "keywords": keywords[: int(highlight.get("max_keywords", 2))],
            "mode": highlight.get("mode", "keyword_badge"),
            "color": highlight.get("highlight_color", "#B45309"),
        }
    return updated


def _build_publish_pack(
    brief: Dict[str, Any],
    mode: str,
    account_pack: Dict[str, Any],
) -> Dict[str, Any]:
    publish = account_pack.get("publish") or {}
    title_template = (publish.get("title_templates") or {}).get(mode) or brief["title"]
    description_template = (publish.get("description_templates") or {}).get(mode)
    description_template = description_template or (publish.get("description_templates") or {}).get("default", "")
    hashtags = (publish.get("hashtags") or {}).get(mode) or (publish.get("hashtags") or {}).get("default", [])
    title = title_template.format(topic=brief["topic"])
    description = description_template.format(topic=brief["topic"])
    return {
        "title": title[: int(publish.get("title_max_length", 30))],
        "cover_text": brief["topic"][: int(publish.get("cover_text_max_length", 12))],
        "description": description,
        "hashtags": hashtags,
    }


def _topic_id(topic: str, scene: str) -> str:
    return hashlib.md5(f"metaphysics:{scene}:{topic}".encode("utf-8")).hexdigest()[:12]
