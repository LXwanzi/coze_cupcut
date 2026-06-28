"""Metaphysics account script generation."""

import hashlib
from typing import Any, Dict, List


MONEY_KEYWORDS = ["钱留不住", "漏财", "守财", "花钱", "存不住钱", "财"]
DEFAULT_WEAK_HOOK_PHRASES = ["先别急着焦虑", "适合先收藏", "慢慢看"]


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
    quality_review = _review_brief(brief, account_pack)
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
        "quality_review": quality_review,
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
            "quick_review": brief["avoid_mistake"],
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
    clean_topic = topic.replace("玄学方向", "").strip() or topic
    concrete_signs = _symptoms_for_topic(clean_topic, scene)
    sharp_claim = _sharp_hook_for_topic(clean_topic, concrete_signs)
    if any(keyword in clean_topic for keyword in MONEY_KEYWORDS):
        hidden_mechanism = "钱不是一下子漏掉的，是在一次次不用想就付款里流走的。"
        mystic_view = "传统说法里，这种状态容易被叫作财气不聚。"
        real_life_view = "现实一点说，是钱出去前，少了一个让你停下来的动作。"
        micro_adjustments = [
            "付款前先停十秒，问自己是不是真的需要。",
            "每天清一次钱包和玄关，只留当天真正有用的东西。",
        ]
        avoid_mistake = "别一边喊守财，一边把每一次付款都变成顺手动作。"
        interaction = "你最容易在哪一刻忍不住付款？"
    else:
        hidden_mechanism = "状态不是突然乱掉的，是小杂事一直没被收回来。"
        mystic_view = "传统说法里，状态不稳时先看空间和随身物件的秩序感。"
        real_life_view = "现实一点说，是你每天看到的东西都在提醒你还没处理完。"
        micro_adjustments = [
            "先清掉最常看到的一处杂物。",
            "给每天出门前的自己留一个干净位置。",
        ]
        avoid_mistake = "别一边想稳住状态，一边让最常看的地方一直乱着。"
        interaction = "你最想先整理钱包、玄关，还是桌面？"
    return {
        "topic": clean_topic,
        "mode": mode,
        "scene": scene,
        "raw_pain": clean_topic,
        "sharp_claim": sharp_claim,
        "hidden_mechanism": hidden_mechanism,
        "concrete_signs": concrete_signs,
        "mystic_view": mystic_view,
        "real_life_view": real_life_view,
        "micro_adjustments": micro_adjustments,
        "avoid_mistake": avoid_mistake,
        "interaction": interaction,
        "title": f"【{clean_topic[:10]}】想稳一点，可以先看这个",
    }


def _build_segments(brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "scene": "强命题",
            "caption": brief["sharp_claim"],
            "tts": brief["sharp_claim"],
            "image_prompt": _image_prompt(brief, "opening", include_product=False),
            "duration": 2.6,
        },
        {
            "scene": "隐藏机制",
            "caption": brief["hidden_mechanism"],
            "tts": brief["hidden_mechanism"],
            "image_prompt": _image_prompt(brief, "life scene", include_product=False),
            "duration": 4.2,
        },
        {
            "scene": "具体动作",
            "caption": "，".join(brief["concrete_signs"][:3]),
            "tts": "看看你有没有这三个动作：" + "，".join(brief["concrete_signs"][:3]) + "。",
            "image_prompt": _image_prompt(brief, "concrete signs", include_product=False),
            "duration": 4.6,
        },
        {
            "scene": "传统说法",
            "caption": brief["mystic_view"],
            "tts": brief["mystic_view"],
            "image_prompt": _image_prompt(brief, "mystic view", include_product=False),
            "duration": 3.8,
        },
        {
            "scene": "现实解释",
            "caption": brief["real_life_view"],
            "tts": brief["real_life_view"],
            "image_prompt": _image_prompt(brief, "real life view", include_product=False),
            "duration": 3.8,
        },
        {
            "scene": "微调整",
            "caption": "\n".join(f"{index}. {item}" for index, item in enumerate(brief["micro_adjustments"], start=1)),
            "tts": "先做两个小调整。" + "".join(brief["micro_adjustments"]),
            "image_prompt": _image_prompt(brief, "micro adjustments", include_product=False),
            "duration": 6.0,
        },
        {
            "scene": "避坑提醒",
            "caption": brief["avoid_mistake"],
            "tts": brief["avoid_mistake"],
            "image_prompt": _image_prompt(brief, "avoid mistake", include_product=False),
            "duration": 3.8,
        },
        {
            "scene": "自然问句",
            "caption": brief["interaction"],
            "tts": brief["interaction"],
            "image_prompt": _image_prompt(brief, "soft interaction", include_product=False),
            "duration": 3.2,
        },
    ]


def _image_prompt(brief: Dict[str, Any], moment: str, include_product: bool = False) -> str:
    life_detail = _life_detail_for_moment(brief, moment)
    base = (
        f"{brief['topic']}, metaphysics lifestyle short video, moment: {moment}, "
        f"{life_detail}, abstract black-gold guardian portrait, lotus halo, incense mist, quiet mystical atmosphere, "
        "no text, no speech bubbles"
    )
    if include_product:
        product_angle = brief.get("product_angle", "matching lucky object")
        return (
            f"{base}, show only one matching product type: {product_angle}, "
            "single product close-up in lower third, no other lucky objects"
        )
    return f"{base}, no product props, no lucky object pile"


def _life_detail_for_moment(brief: Dict[str, Any], moment: str) -> str:
    if moment == "concrete signs":
        return "subtle lifestyle symbols such as mobile payment glow, messy receipts, wallet silhouette and entryway clutter"
    if moment == "micro adjustments":
        return "clean wallet, tidy entryway, calm organizing gesture, no branded product"
    if moment == "avoid mistake":
        return "contrast between messy receipts and a calm dark empty space"
    if moment == "real life view":
        return "a quiet pause before payment, hand near phone but not touching pay button"
    return "minimal symbolic lifestyle scene"


def _symptoms_for_topic(topic: str, scene: str) -> List[str]:
    if any(keyword in topic for keyword in MONEY_KEYWORDS):
        return [
            "刚到账就花掉",
            "付款太随手",
            "买完又后悔",
        ]
    if scene == "bedroom":
        return [
            "睡前脑子停不下来",
            "床头杂物越堆越多",
            "醒来还是觉得累",
        ]
    if scene == "desk":
        return [
            "坐下就分心",
            "桌面越乱越烦",
            "事情总是拖到最后",
        ]
    return [
        "东西越堆越乱",
        "心里总是不踏实",
        "想调整却不知道从哪开始",
    ]


def _sharp_hook_for_topic(topic: str, symptoms: List[str]) -> str:
    if any(keyword in topic for keyword in MONEY_KEYWORDS):
        return "你以为是赚得少，其实是钱出去得太顺手。"
    symptom = symptoms[0] if symptoms else topic
    return f"你以为是自己不够稳，其实是{symptom}太顺手。"


def _review_brief(brief: Dict[str, Any], account_pack: Dict[str, Any]) -> Dict[str, Any]:
    template = (account_pack.get("script_templates") or {}).get(brief.get("mode"), {})
    gate = template.get("quality_gate") or {}
    min_symptoms = int(gate.get("min_symptoms", 2))
    weak_phrases = gate.get("weak_hook_phrases") or DEFAULT_WEAK_HOOK_PHRASES
    forbidden_claims = gate.get("forbidden_claims") or []
    issues: List[str] = []

    if len(brief.get("concrete_signs") or []) < min_symptoms:
        issues.append("具体表现少于质量闸门要求。")
    if any(phrase in brief.get("sharp_claim", "") for phrase in weak_phrases):
        issues.append("开头钩子偏泛，缺少具体命中感。")
    required_patterns = gate.get("required_claim_patterns") or []
    if required_patterns and not any(pattern in brief.get("sharp_claim", "") for pattern in required_patterns):
        issues.append("强命题缺少反差判断。")
    min_adjustments = int(gate.get("min_adjustments", 2))
    if len(brief.get("micro_adjustments") or []) < min_adjustments:
        issues.append("微调整少于质量闸门要求。")
    body = " ".join(str(value) for value in brief.values())
    if any(claim in body for claim in forbidden_claims):
        issues.append("包含玄学绝对化承诺。")

    return {
        "is_reasonable": not issues,
        "issues": issues,
        "slots": template.get("required_slots", []),
    }


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
