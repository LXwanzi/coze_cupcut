"""
Topic-only rescue script generation.

Turns a short Chinese topic such as "机场值机" into a structured short-video
brief and ready-to-render segments. The output keeps the current downstream
TTS/image/CapCut nodes unchanged.
"""

import hashlib
import re
from typing import Any, Dict, List

from content.account_loader import get_account_pack


DEFAULT_TOPIC_DURATION_SECONDS = 30
DEFAULT_TOPIC_SENTENCE_COUNT = 3
SCENE_COLLECTION_DURATION_SECONDS = 38

DEFAULT_PAINPOINT_TRIGGERS = [
    "别说", "不要说", "中式英语", "不会说", "说错", "怎么说", "不是",
    "容易说错", "只会说", "救场",
]

DEFAULT_MODE_ALIASES = {
    "场景式": "scene_collection",
    "场景": "scene_collection",
    "合集": "scene_collection",
    "痛点式": "painpoint_contrast",
    "痛点": "painpoint_contrast",
    "反差": "painpoint_contrast",
    "纠错": "painpoint_contrast",
}

ACCOUNT_PACK = get_account_pack()
MODE_ALIASES = ACCOUNT_PACK.get("modes", {}).get("mode_aliases") or DEFAULT_MODE_ALIASES
PAINPOINT_TRIGGERS = ACCOUNT_PACK.get("modes", {}).get("painpoint_triggers") or DEFAULT_PAINPOINT_TRIGGERS
SCENE_MAP = ACCOUNT_PACK.get("modes", {}).get("scene_map") or [
    ["emergency", ["救场", "卡壳", "听不清", "不会说", "付款失败", "迷路", "丢东西"]],
    ["hotel", ["酒店", "入住", "退房", "房间", "前台", "押金", "早餐"]],
    ["office", ["办公室", "开会", "请假", "催进度", "汇报", "同事", "进度"]],
    ["business", ["商务", "客户", "合同", "谈判", "报价", "提案"]],
    ["parent_child", ["亲子", "孩子", "绘本", "睡前"]],
    ["daily", ["日常", "生活", "咖啡", "外卖", "超市", "理发"]],
    ["travel", ["旅行", "机场", "入境", "航班", "行李", "登机", "护照", "值机"]],
]
VOICE_PROFILES = ACCOUNT_PACK.get("modes", {}).get("voice_profiles") or {}
GENERIC_SCENE_EXPRESSIONS = {
    "excuse me could you help me",
    "could you help me",
    "could you help me with this",
    "id like to ask about this",
    "could you confirm that for me",
    "could you say that again",
    "thanks that helps a lot",
    "thank you that helps a lot",
}


def _configured_presets(key: str) -> List[Dict[str, Any]]:
    presets = ACCOUNT_PACK.get(key)
    return presets if isinstance(presets, list) else []


TOPIC_PRESETS: List[Dict[str, Any]] = _configured_presets("painpoint_presets")
SCENE_COLLECTION_PRESETS: List[Dict[str, Any]] = _configured_presets("scene_collection_presets")


def parse_topic_input(raw_text: str) -> Dict[str, Any]:
    """Parse a user-supplied short topic into routing metadata."""
    topic = (raw_text or "").strip()
    explicit_mode, clean_topic = extract_explicit_mode(topic)
    scene_preset = find_scene_collection_preset(clean_topic)
    preset = find_topic_preset(clean_topic)
    content_mode = explicit_mode or classify_content_mode(clean_topic, scene_preset=scene_preset, painpoint_preset=preset)
    selected = scene_preset if content_mode == "scene_collection" and scene_preset else preset
    return {
        "raw_topic": clean_topic,
        "topic": selected.get("topic") if selected else clean_topic,
        "scene": selected.get("scene") if selected else detect_scene(clean_topic),
        "sub_scene": selected.get("sub_scene") if selected else slugify_topic(clean_topic),
        "content_mode": content_mode,
        "primary_mode": content_mode,
        "secondary_mode": "immersive_follow_read",
        "ending_mode": "checkin_challenge",
        "auto_generate_expressions": True,
    }


def build_topic_brief(
    raw_topic: str,
    memory_context: Dict[str, Any] | None = None,
    content_mode: str | None = None
) -> Dict[str, Any]:
    """Build a concrete one-video brief from a broad topic."""
    memory_context = memory_context or {}
    explicit_mode, clean_topic = extract_explicit_mode(raw_topic)
    selected_mode = content_mode or explicit_mode or classify_content_mode(clean_topic)

    if selected_mode == "scene_collection":
        preset = select_scene_collection_preset(clean_topic, memory_context)
        brief = (
            {k: v for k, v in preset.items() if k != "keywords"}
            if preset else build_dynamic_scene_collection_stub(clean_topic)
        )
        brief["content_mode"] = "scene_collection"
    else:
        preset = select_topic_preset(clean_topic, memory_context)
        if preset:
            brief = {k: v for k, v in preset.items() if k != "keywords"}
        else:
            topic = (clean_topic or "真实场景英语").strip()
            brief = build_fallback_brief(topic)
        brief["content_mode"] = "painpoint_contrast"

    brief["raw_topic"] = clean_topic
    brief["quality_review"] = review_topic_brief(brief, clean_topic)
    brief["voice_profile"] = voice_profile_for_mode(brief.get("content_mode"), brief.get("scene"))
    brief["topic_id"] = generate_topic_id(brief.get("topic", clean_topic), brief.get("scene", "travel"))
    return brief


def normalize_dynamic_scene_collection_brief(
    raw_topic: str,
    scene: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Normalize LLM-generated scene collection data into a renderable brief."""
    topic = (payload.get("topic") or raw_topic or "真实场景英语").strip()
    expressions = []
    for item in payload.get("expressions", []):
        if not isinstance(item, dict):
            continue
        english = (item.get("english") or "").strip()
        chinese = (item.get("chinese") or "").strip()
        if not english or not chinese:
            continue
        expressions.append({
            "label": (item.get("label") or f"第{len(expressions) + 1}句").strip(),
            "english": english,
            "chinese": chinese,
            "usage": (item.get("usage") or "").strip(),
        })

    brief = {
        "id": slugify_topic(topic),
        "scene": scene or detect_scene(raw_topic),
        "sub_scene": slugify_topic(topic),
        "topic": topic,
        "raw_topic": raw_topic,
        "real_scene": (payload.get("real_scene") or f"{topic}这个具体场景").strip(),
        "hook": (payload.get("hook") or f"{topic}，这 5 句先收藏。").strip(),
        "setup": (payload.get("setup") or f"围绕{topic}，只学真实能用的表达。").strip(),
        "expressions": expressions[:5],
        "summary_tts": (payload.get("summary_tts") or f"这 5 句先收藏，{topic}时可以直接用。").strip(),
        "next_preview": (payload.get("next_preview") or f"下集继续讲{topic}里的高频表达。").strip(),
        "interaction": (payload.get("interaction") or f"你在{topic}还卡过哪句？评论区说说。").strip(),
        "title": (payload.get("title") or f"【{topic[:10]}】这5句真的能救场").strip(),
        "content_mode": "scene_collection",
        "source": "dynamic_llm",
    }
    brief["quality_review"] = review_topic_brief(brief, raw_topic)
    brief["voice_profile"] = voice_profile_for_mode(brief.get("content_mode"), brief.get("scene"))
    brief["topic_id"] = generate_topic_id(brief.get("topic", raw_topic), brief.get("scene", "travel"))
    return brief


def build_scene_collection_segments(
    brief: Dict[str, Any],
    duration_seconds: int = SCENE_COLLECTION_DURATION_SECONDS
) -> List[Dict[str, Any]]:
    """Build a compact 4-5 sentence same-scene collection script."""
    expressions = (brief.get("expressions") or [])[:5]
    segments: List[Dict[str, Any]] = [
        {
            "scene": "钩子页",
            "caption": brief.get("hook", f"{brief.get('topic', '这个场景')}，这几句先收藏。"),
            "tts": brief.get("hook", f"{brief.get('topic', '这个场景')}，这几句先收藏。"),
            "image_prompt": "FIXED_HOOK_IMAGE",
            "duration": 2.0,
        },
        {
            "scene": "场景代入",
            "caption": brief.get("setup", brief.get("real_scene", "")),
            "tts": brief.get("setup", brief.get("real_scene", "")),
            "image_prompt": _scene_prompt(brief, "real scene setup"),
            "duration": 3.0,
        },
    ]

    for index, expression in enumerate(expressions, start=1):
        segments.append({
            "scene": f"第{index}句场景句",
            "caption": f"{expression.get('english', '')}\n{expression.get('chinese', '')}".strip(),
            "tts": build_collection_sentence_tts(index, expression),
            "image_prompt": _scene_prompt(brief, expression.get("label", f"sentence {index}")),
            "duration": 4.8,
        })

    summary_caption = "\n".join(
        f"{idx}. {item.get('english', '')}"
        for idx, item in enumerate(expressions, start=1)
    )
    segments.extend([
        {
            "scene": "快速汇总页",
            "caption": summary_caption,
            "tts": brief.get("summary_tts", "这 5 句先收藏，下一集继续学同一场景。"),
            "image_prompt": "FIXED_REVIEW_WITH_CHAR",
            "duration": 3.0,
        },
        {
            "scene": "互动页",
            "caption": brief.get("interaction", "你还卡过哪句？评论区说说。"),
            "tts": brief.get("interaction", "你还卡过哪句？评论区说说。"),
            "image_prompt": "FIXED_HOOK_IMAGE",
            "duration": 2.0,
        },
    ])

    return validate_scene_collection_segments(segments, duration_seconds=duration_seconds)


def build_rescue_segments(
    brief: Dict[str, Any],
    duration_seconds: int = DEFAULT_TOPIC_DURATION_SECONDS
) -> List[Dict[str, Any]]:
    """Build ready-to-render segments for the hybrid rescue format."""
    answer_levels = brief.get("answer_levels") or []
    survival = _answer_by_level(answer_levels, "survival")
    standard = _answer_by_level(answer_levels, "standard") or survival
    polite = _answer_by_level(answer_levels, "polite")
    follow_read = standard or survival or polite or {}

    segments = [
        {
            "scene": "钩子页",
            "caption": brief.get("pain_point", "这句英语，别再说错"),
            "tts": brief.get("pain_point", "这句英语，别再说错。"),
            "image_prompt": "FIXED_HOOK_IMAGE",
            "duration": 2.0,
        },
        {
            "scene": "沉浸场景",
            "caption": f"{brief.get('staff_line', '')}\n{brief.get('staff_line_cn', '')}".strip(),
            "tts": build_scene_tts(brief),
            "image_prompt": _scene_prompt(brief, "conversation"),
            "duration": 4.0,
        },
        {
            "scene": "错误表达",
            "caption": f"{brief.get('wrong_expression', '')}\n{brief.get('why_wrong', '')}".strip(),
            "tts": f"别说 {brief.get('wrong_expression', '')}。{brief.get('why_wrong', '')}",
            "image_prompt": _scene_prompt(brief, "mistake"),
            "duration": 4.0,
        },
        _answer_segment("最短能救场", survival, brief, 4.0),
        _answer_segment("完整一点", standard, brief, 4.5),
    ]

    if polite and polite.get("english") != standard.get("english"):
        segments.append(_answer_segment(polite.get("label", "更自然一点"), polite, brief, 4.5))

    segments.extend([
        {
            "scene": "跟读打卡",
            "caption": f"{follow_read.get('english', '')}\n跟小丸子读一遍".strip(),
            "tts": f"跟小丸子读一遍：{follow_read.get('english', '')}",
            "image_prompt": _scene_prompt(brief, "follow read"),
            "duration": 4.0,
        },
        {
            "scene": "预告页",
            "caption": brief.get("interaction", "你还卡过哪句？评论区告诉我。"),
            "tts": brief.get("interaction", "你还卡过哪句？评论区告诉我。"),
            "image_prompt": "FIXED_HOOK_IMAGE",
            "duration": 2.0,
        },
    ])

    return validate_rescue_segments(segments, duration_seconds=duration_seconds)


def validate_rescue_segments(
    segments: List[Dict[str, Any]],
    duration_seconds: int = DEFAULT_TOPIC_DURATION_SECONDS
) -> List[Dict[str, Any]]:
    """Apply hard guardrails for retention-oriented rescue scripts."""
    cleaned: List[Dict[str, Any]] = []
    running_duration = 0.0
    max_duration = max(duration_seconds, 24)

    for segment in segments:
        if not segment:
            continue
        item = dict(segment)
        item["tts"] = sanitize_tts(item.get("tts", ""))
        if item.get("scene") != "预告页":
            item["caption"] = compact_caption(item.get("caption", ""), max_lines=2)
        else:
            item["caption"] = compact_caption(item.get("caption", ""), max_lines=2)
        item["duration"] = min(float(item.get("duration", 4.0)), 5.0)
        running_duration += item["duration"]
        if running_duration <= max_duration or item.get("scene") == "预告页":
            cleaned.append(item)

    if not any(seg.get("scene") == "预告页" for seg in cleaned):
        cleaned.append({
            "scene": "预告页",
            "caption": "你还卡过哪句？评论区告诉我。",
            "tts": "你还卡过哪句？评论区告诉我。",
            "image_prompt": "FIXED_HOOK_IMAGE",
            "duration": 2.0,
        })

    return cleaned


def extract_answer_sentences(brief: Dict[str, Any]) -> List[str]:
    if brief.get("expressions"):
        return [
            item.get("english", "").strip()
            for item in brief.get("expressions", [])
            if item.get("english")
        ]
    return [
        item.get("english", "").strip()
        for item in brief.get("answer_levels", [])
        if item.get("english")
    ]


def extract_explicit_mode(topic: str) -> tuple[str | None, str]:
    """Read optional mode prefixes such as 场景式：机场值机."""
    text = (topic or "").strip()
    if "：" in text or ":" in text:
        separator = "：" if "：" in text else ":"
        prefix, rest = text.split(separator, 1)
        prefix = prefix.strip()
        if prefix in MODE_ALIASES:
            return MODE_ALIASES[prefix], rest.strip()
    return None, text


def classify_content_mode(
    topic: str,
    scene_preset: Dict[str, Any] | None = None,
    painpoint_preset: Dict[str, Any] | None = None
) -> str:
    """Choose scene collection vs pain-point contrast from the user's topic."""
    text = (topic or "").strip()
    if any(trigger in text for trigger in PAINPOINT_TRIGGERS):
        return "painpoint_contrast"
    if scene_preset or find_scene_collection_preset(text):
        return "scene_collection"
    if painpoint_preset or find_topic_preset(text):
        return "painpoint_contrast"
    if re.search(r"[A-Za-z]{2,}.*[/／].*[\u4e00-\u9fff]", text):
        return "scene_collection"
    if len(extract_expression_lines(text)) >= 3:
        return "scene_collection"
    return "painpoint_contrast"


def extract_expression_lines(text: str) -> List[str]:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return [line for line in lines if re.search(r"[A-Za-z]{2,}", line)]


def find_scene_collection_preset(topic: str) -> Dict[str, Any] | None:
    topic_lower = (topic or "").lower()
    for preset in SCENE_COLLECTION_PRESETS:
        if any(keyword.lower() in topic_lower for keyword in preset["keywords"]):
            return preset
    return None


def select_scene_collection_preset(raw_topic: str, memory_context: Dict[str, Any]) -> Dict[str, Any] | None:
    topic_lower = (raw_topic or "").lower()
    candidates = [
        preset for preset in SCENE_COLLECTION_PRESETS
        if any(keyword.lower() in topic_lower for keyword in preset["keywords"])
    ]
    if not candidates:
        return None

    used_scenes = set(memory_context.get("scenes_used", []))
    for preset in candidates:
        if preset.get("hook") not in used_scenes and preset.get("topic") not in used_scenes:
            return preset
    return candidates[0]


def review_topic_brief(brief: Dict[str, Any], raw_topic: str) -> Dict[str, Any]:
    """Lightweight script quality gate before rendering."""
    mode = brief.get("content_mode", "painpoint_contrast")
    issues: List[str] = []
    suggestions: List[str] = []

    if mode == "scene_collection":
        expressions = brief.get("expressions") or []
        if brief.get("needs_dynamic_generation"):
            issues.append("场景式主题未命中预设，需要动态生成具体表达。")
            suggestions.append("调用动态场景生成器，禁止直接使用万能句兜底。")
        if len(expressions) < 4:
            issues.append("场景式内容少于 4 句，收藏价值偏弱。")
            suggestions.append("补足到同一场景下 4-5 个连续动作。")
        if len(expressions) > 5:
            issues.append("场景式内容超过 5 句，容易拖慢完播。")
            suggestions.append("只保留同一场景里最刚需的 5 句。")
        if _looks_cross_scene(brief):
            issues.append("句子疑似跨了多个场景。")
            suggestions.append("拆成多条视频，单条只讲一个具体场景。")
        generic_items = find_generic_scene_expressions(expressions)
        if generic_items and (brief.get("source") == "dynamic_llm" or len(generic_items) >= 2):
            issues.append(f"场景式内容包含万能句：{', '.join(generic_items[:3])}")
            suggestions.append("改成和用户主题强相关的具体动作句，不能用万能求助/确认句凑数。")
        if expressions and brief.get("source") == "dynamic_llm" and not _has_topic_overlap(raw_topic, expressions):
            issues.append("句子和用户主题关键词关联偏弱。")
            suggestions.append("重新生成，确保每句都能直接用于用户描述的具体场景。")
        target_duration = SCENE_COLLECTION_DURATION_SECONDS
        suggested_sentence_count = min(max(len(expressions), 4), 5) if expressions else 5
    else:
        answer_levels = brief.get("answer_levels") or []
        if len(answer_levels) < 2:
            issues.append("痛点式内容缺少分层正确表达。")
            suggestions.append("至少保留最短救场句和完整表达。")
        if not brief.get("wrong_expression"):
            issues.append("痛点式内容缺少错误表达，反差不够强。")
            suggestions.append("补一个大家常说错的中式表达。")
        target_duration = DEFAULT_TOPIC_DURATION_SECONDS
        suggested_sentence_count = min(max(len(answer_levels), 2), 3) if answer_levels else 3

    return {
        "is_reasonable": not issues,
        "content_mode": mode,
        "topic": brief.get("topic", raw_topic),
        "suggested_sentence_count": suggested_sentence_count,
        "target_duration_seconds": target_duration,
        "issues": issues,
        "suggestions": suggestions,
    }


def voice_profile_for_mode(content_mode: str | None, scene: str | None = None) -> Dict[str, Any]:
    """Recommend TTS voice and speed for each short-video format."""
    if scene in VOICE_PROFILES:
        return VOICE_PROFILES[scene]
    if content_mode in VOICE_PROFILES:
        return VOICE_PROFILES[content_mode]
    return VOICE_PROFILES.get(
        "default",
        {"voice": "vivi", "speed": 1.08, "style": "clear_bilingual"}
    )


def build_collection_sentence_tts(index: int, expression: Dict[str, Any]) -> str:
    label = expression.get("label", f"第 {index} 句")
    english = expression.get("english", "")
    chinese = expression.get("chinese", "")
    return sanitize_tts(f"第 {index} 句，{label}：{english}。{chinese}")


def validate_scene_collection_segments(
    segments: List[Dict[str, Any]],
    duration_seconds: int = SCENE_COLLECTION_DURATION_SECONDS
) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    running_duration = 0.0
    max_duration = max(duration_seconds, 34)

    for segment in segments:
        if not segment:
            continue
        item = dict(segment)
        item["tts"] = sanitize_tts(item.get("tts", ""))
        if item.get("scene") == "快速汇总页":
            item["caption"] = compact_caption(item.get("caption", ""), max_lines=5)
            item["duration"] = min(float(item.get("duration", 3.0)), 3.0)
        elif item.get("scene") in ["钩子页", "互动页"]:
            item["caption"] = compact_caption(item.get("caption", ""), max_lines=2)
            item["duration"] = min(float(item.get("duration", 2.0)), 2.5)
        else:
            item["caption"] = compact_caption(item.get("caption", ""), max_lines=2)
            item["duration"] = min(float(item.get("duration", 4.8)), 5.0)
        running_duration += item["duration"]
        if running_duration <= max_duration or item.get("scene") == "互动页":
            cleaned.append(item)

    if not any(seg.get("scene") == "互动页" for seg in cleaned):
        cleaned.append({
            "scene": "互动页",
            "caption": "你还卡过哪句？评论区说说。",
            "tts": "你还卡过哪句？评论区说说。",
            "image_prompt": "FIXED_HOOK_IMAGE",
            "duration": 2.0,
        })

    return cleaned


def _looks_cross_scene(brief: Dict[str, Any]) -> bool:
    text = " ".join(
        [
            brief.get("topic", ""),
            brief.get("real_scene", ""),
            " ".join(item.get("label", "") for item in brief.get("expressions", [])),
        ]
    )
    scene_hits = {
        scene for scene, keywords in [
            ("airport", ["机场", "值机", "登机口", "托运"]),
            ("plane", ["飞机", "空乘", "毯子", "座位屏幕"]),
            ("hotel", ["酒店", "退房", "账单", "房间"]),
            ("office", ["办公室", "会议", "同事", "进度"]),
        ]
        if any(keyword in text for keyword in keywords)
    }
    allowed_pairs = {frozenset(["airport", "plane"])}
    if len(scene_hits) <= 1:
        return False
    return frozenset(scene_hits) not in allowed_pairs


def find_generic_scene_expressions(expressions: List[Dict[str, Any]]) -> List[str]:
    generic = []
    for item in expressions:
        english = _normalize_english_for_match(item.get("english", ""))
        if english in GENERIC_SCENE_EXPRESSIONS:
            generic.append(item.get("english", "").strip())
    return generic


def _has_topic_overlap(raw_topic: str, expressions: List[Dict[str, Any]]) -> bool:
    topic_tokens = _topic_tokens(raw_topic)
    if not topic_tokens:
        return True
    expression_text = " ".join(
        f"{item.get('label', '')} {item.get('english', '')} {item.get('chinese', '')} {item.get('usage', '')}"
        for item in expressions
    ).lower()
    return any(token.lower() in expression_text for token in topic_tokens)


def _topic_tokens(text: str) -> List[str]:
    text = (text or "").strip()
    tokens = []
    zh_keywords = [
        "飞机餐", "忌口", "过敏", "素食", "花生", "海鲜", "猪肉", "鸡肉",
        "行李", "托运", "值机", "空乘", "酒店", "账单", "退房", "早餐",
        "入境", "办公室", "会议", "咖啡", "外卖",
    ]
    tokens.extend(keyword for keyword in zh_keywords if keyword in text)
    tokens.extend(re.findall(r"[A-Za-z]{3,}", text))
    if tokens:
        return tokens
    return [text] if len(text) <= 8 else []


def _normalize_english_for_match(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def find_topic_preset(topic: str) -> Dict[str, Any] | None:
    topic_lower = (topic or "").lower()
    for preset in TOPIC_PRESETS:
        if any(keyword.lower() in topic_lower for keyword in preset["keywords"]):
            return preset
    return None


def select_topic_preset(raw_topic: str, memory_context: Dict[str, Any]) -> Dict[str, Any] | None:
    topic_lower = (raw_topic or "").lower()
    candidates = [
        preset for preset in TOPIC_PRESETS
        if any(keyword.lower() in topic_lower for keyword in preset["keywords"])
    ]
    if not candidates:
        return None

    used_hooks = set(memory_context.get("used_pain_points", []))
    scenes_used = set(memory_context.get("scenes_used", []))
    for preset in candidates:
        if preset.get("pain_point") not in used_hooks and preset.get("pain_point") not in scenes_used:
            return preset
    return candidates[0]


def detect_scene(text: str) -> str:
    text = text or ""
    for scene, keywords in SCENE_MAP:
        if any(keyword in text for keyword in keywords):
            return scene
    return "travel"


def generate_topic_id(topic: str, scene: str) -> str:
    key = f"{scene}_{slugify_topic(topic)}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def slugify_topic(topic: str) -> str:
    topic = (topic or "topic").strip().lower()
    topic = re.sub(r"\s+", "_", topic)
    topic = re.sub(r"[^\w\u4e00-\u9fff-]", "", topic)
    return topic[:32] or "topic"


def build_fallback_brief(topic: str) -> Dict[str, Any]:
    scene = detect_scene(topic)
    return {
        "id": slugify_topic(topic),
        "scene": scene,
        "sub_scene": slugify_topic(topic),
        "topic": topic,
        "real_scene": f"{topic}这个真实场景里，你需要对方处理一个具体需求",
        "staff_line": "How can I help you?",
        "staff_line_cn": "有什么可以帮你？",
        "pain_point": f"{topic}时，别只会说 help me",
        "wrong_expression": "Help me.",
        "why_wrong": "这句太空，对方不知道你到底要查、改、拿还是确认什么。",
        "communication_intent": f"在{topic}场景里说清楚具体需求",
        "answer_levels": [
            {
                "level": "survival",
                "label": "最短能救场",
                "english": "Could you help me with this?",
                "chinese": "可以帮我处理一下这个吗？",
                "usage": "先把求助意图说完整。",
            },
            {
                "level": "standard",
                "label": "完整一点",
                "english": "Could you check this for me?",
                "chinese": "可以帮我检查一下这个吗？",
                "usage": "需要对方查看或确认时用。",
            },
            {
                "level": "polite",
                "label": "更具体一点",
                "english": "Could you help me figure out what I should do next?",
                "chinese": "可以帮我看看下一步该怎么处理吗？",
                "usage": "不知道流程时，比单说 help me 更能推进事情。",
            },
        ],
        "next_preview": f"下集继续讲{topic}里的卡壳表达。",
        "interaction": f"你在{topic}还卡过哪句？评论区告诉我。",
    }


def build_dynamic_scene_collection_stub(topic: str) -> Dict[str, Any]:
    scene = detect_scene(topic)
    return {
        "id": slugify_topic(topic),
        "scene": scene,
        "sub_scene": slugify_topic(topic),
        "topic": topic,
        "real_scene": f"{topic}这个具体场景",
        "hook": f"{topic}，这 5 句先收藏。",
        "setup": f"围绕{topic}，只学真实能用的表达。",
        "expressions": [],
        "summary_tts": f"这 5 句先收藏，{topic}时可以直接用。",
        "next_preview": f"下集继续讲{topic}里的高频卡壳句。",
        "interaction": f"你在{topic}还卡过哪句？评论区说说。",
        "title": f"【{topic[:8]}】不会开口？这5句能救场",
        "needs_dynamic_generation": True,
    }


def sanitize_tts(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"再来一遍[:：]?.*$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def build_scene_tts(brief: Dict[str, Any]) -> str:
    """Build immersive scene narration without duplicated location prefixes."""
    real_scene = (brief.get("real_scene") or "真实场景里").strip()
    real_scene = re.sub(r"^(现在)?你在", "", real_scene).strip("，。 ")
    staff_line = (brief.get("staff_line") or "").strip()
    if staff_line:
        return f"现在你在{real_scene}。对方问：{staff_line}"
    return f"现在你在{real_scene}。"


def compact_caption(caption: str, max_lines: int = 2) -> str:
    lines = [line.strip() for line in (caption or "").splitlines() if line.strip()]
    return "\n".join(lines[:max_lines])


def _answer_by_level(answer_levels: List[Dict[str, Any]], level: str) -> Dict[str, Any]:
    for item in answer_levels:
        if item.get("level") == level:
            return item
    return {}


def _answer_segment(
    scene_name: str,
    answer: Dict[str, Any],
    brief: Dict[str, Any],
    duration: float
) -> Dict[str, Any]:
    return {
        "scene": scene_name,
        "caption": f"{answer.get('english', '')}\n{answer.get('chinese', '')}".strip(),
        "tts": f"{scene_name}：{answer.get('english', '')}。{answer.get('chinese', '')}",
        "image_prompt": _scene_prompt(brief, answer.get("level", scene_name)),
        "duration": duration,
    }


def _scene_prompt(brief: Dict[str, Any], moment: str) -> str:
    return (
        f"{brief.get('topic', 'English scene')}, {brief.get('real_scene', '')}, "
        f"moment: {moment}, Xiao Wanzi helping a young office worker speak English, "
        "minimal props, clear real-life setting"
    )
