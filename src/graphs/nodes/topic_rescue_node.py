"""
Topic-only rescue script generation.

Turns a short Chinese topic such as "机场值机" into a structured short-video
brief and ready-to-render segments. The output keeps the current downstream
TTS/image/CapCut nodes unchanged.
"""

import hashlib
import re
from typing import Any, Dict, List


DEFAULT_TOPIC_DURATION_SECONDS = 30
DEFAULT_TOPIC_SENTENCE_COUNT = 3
SCENE_COLLECTION_DURATION_SECONDS = 38

PAINPOINT_TRIGGERS = [
    "别说", "不要说", "中式英语", "不会说", "说错", "怎么说", "不是",
    "容易说错", "只会说", "救场",
]

MODE_ALIASES = {
    "场景式": "scene_collection",
    "场景": "scene_collection",
    "合集": "scene_collection",
    "痛点式": "painpoint_contrast",
    "痛点": "painpoint_contrast",
    "反差": "painpoint_contrast",
    "纠错": "painpoint_contrast",
}


TOPIC_PRESETS: List[Dict[str, Any]] = [
    {
        "id": "airport_checkin_bag",
        "keywords": ["机场值机", "值机", "托运行李", "行李托运", "check in", "check-in"],
        "scene": "travel",
        "sub_scene": "airport_checkin",
        "topic": "机场值机",
        "real_scene": "你在机场值机柜台，工作人员问你有没有托运行李",
        "staff_line": "Do you have any bags to check?",
        "staff_line_cn": "你有托运行李吗？",
        "pain_point": "机场托运行李，别说 send my bag",
        "wrong_expression": "I want to send my bag.",
        "why_wrong": "send 更像寄包裹，不是机场托运行李。",
        "communication_intent": "回答自己有一个包要托运",
        "answer_levels": [
            {
                "level": "survival",
                "label": "最短能救场",
                "english": "Yes, one bag.",
                "chinese": "有，一个包。",
                "usage": "听懂问题后先接住，不用憋完整句。",
            },
            {
                "level": "standard",
                "label": "完整一点",
                "english": "I have one bag to check.",
                "chinese": "我有一个包要托运。",
                "usage": "回答工作人员询问时最自然。",
            },
            {
                "level": "polite",
                "label": "想主动说",
                "english": "I'd like to check this bag.",
                "chinese": "我想托运这个包。",
                "usage": "主动提出要托运行李时用。",
            },
        ],
        "next_preview": "下集讲选座别说 window place。",
        "interaction": "你在机场遇到过哪些英语卡壳？评论区说说。",
    },
    {
        "id": "plane_attendant_help_painpoint",
        "keywords": [
            "飞机上找空乘", "飞机上找空姐", "找空乘", "找空姐",
            "飞机上求助", "飞机上寻求帮助", "飞机上寻求空乘帮助",
            "空乘帮忙", "空乘帮助", "寻求空乘帮助", "叫空乘帮忙", "找空乘帮忙",
        ],
        "scene": "travel",
        "sub_scene": "in_flight_attendant",
        "topic": "飞机上找空乘",
        "real_scene": "你在飞机上，空乘问你需不需要帮助",
        "staff_line": "Do you need any help?",
        "staff_line_cn": "你需要帮忙吗？",
        "pain_point": "飞机上找空乘，别只会说 yes",
        "wrong_expression": "Yes.",
        "why_wrong": "yes 只表示要，但没说清楚你要对方帮什么。",
        "communication_intent": "明确说出自己需要空乘帮忙的具体事情",
        "answer_levels": [
            {
                "level": "survival",
                "label": "最短能救场",
                "english": "Could you help me?",
                "chinese": "可以帮我一下吗？",
                "usage": "先把求助意图说清楚。",
            },
            {
                "level": "standard",
                "label": "完整一点",
                "english": "Could you help me put this up?",
                "chinese": "可以帮我把这个放上去吗？",
                "usage": "指着行李说 this，比只说 yes 有用得多。",
            },
            {
                "level": "polite",
                "label": "更具体一点",
                "english": "Could you help me put my bag in the overhead bin?",
                "chinese": "可以帮我把包放进行李架吗？",
                "usage": "对方能立刻知道你需要什么帮助。",
            },
        ],
        "next_preview": "下集讲飞机上要水和毯子怎么说。",
        "interaction": "你在飞机上最怕哪句英语卡住？评论区说说。",
    },
    {
        "id": "hotel_checkout_bill",
        "keywords": ["酒店退房", "退房", "账单", "check out", "checkout"],
        "scene": "hotel",
        "sub_scene": "hotel_checkout",
        "topic": "酒店退房",
        "real_scene": "你在酒店前台退房，想确认账单有没有多收费",
        "staff_line": "Would you like to check the bill?",
        "staff_line_cn": "你要核对一下账单吗？",
        "pain_point": "退房看账单，别只说 bill problem",
        "wrong_expression": "The bill has a problem.",
        "why_wrong": "能听懂，但太硬，前台场景不够自然。",
        "communication_intent": "礼貌地请前台帮你核对账单",
        "answer_levels": [
            {
                "level": "survival",
                "label": "最短能救场",
                "english": "Could you check this?",
                "chinese": "能帮我看一下吗？",
                "usage": "先把问题递给前台。",
            },
            {
                "level": "standard",
                "label": "完整一点",
                "english": "Could you check the bill for me?",
                "chinese": "可以帮我核对一下账单吗？",
                "usage": "退房时最稳妥。",
            },
            {
                "level": "polite",
                "label": "更具体一点",
                "english": "I think there is an extra charge here.",
                "chinese": "我觉得这里多收了一项费用。",
                "usage": "指出具体多收费时用。",
            },
        ],
        "next_preview": "下集讲押金没退怎么说。",
        "interaction": "你退房时遇到过什么账单问题？评论区说说。",
    },
    {
        "id": "room_too_noisy",
        "keywords": ["房间太吵", "太吵", "安静房间", "换房"],
        "scene": "hotel",
        "sub_scene": "quiet_room",
        "topic": "房间太吵",
        "real_scene": "你入住后发现房间太吵，想请前台换一个安静点的房间",
        "staff_line": "How can I help you?",
        "staff_line_cn": "有什么可以帮您？",
        "pain_point": "房间太吵，别只会说 too noisy",
        "wrong_expression": "My room is too noisy.",
        "why_wrong": "这句能用，但后面最好接具体请求，不然对方不知道你想要什么。",
        "communication_intent": "请求换到安静一点的房间",
        "answer_levels": [
            {
                "level": "survival",
                "label": "最短能救场",
                "english": "It's too noisy.",
                "chinese": "太吵了。",
                "usage": "先说明问题。",
            },
            {
                "level": "standard",
                "label": "完整一点",
                "english": "Could I have a quieter room?",
                "chinese": "可以给我一间安静点的房间吗？",
                "usage": "直接提出换房需求。",
            },
            {
                "level": "polite",
                "label": "更礼貌一点",
                "english": "Would it be possible to move to a quieter room?",
                "chinese": "可以换到安静一点的房间吗？",
                "usage": "更委婉，适合酒店前台。",
            },
        ],
        "next_preview": "下集讲空调坏了怎么说。",
        "interaction": "你住酒店最怕遇到什么问题？评论区说说。",
    },
    {
        "id": "immigration_purpose",
        "keywords": ["入境", "入境目的", "海关", "来干嘛"],
        "scene": "travel",
        "sub_scene": "immigration",
        "topic": "入境被问目的",
        "real_scene": "你在入境柜台，工作人员问你来这里做什么",
        "staff_line": "What's the purpose of your visit?",
        "staff_line_cn": "你此行目的是什么？",
        "pain_point": "入境被问目的，别只会说 travel",
        "wrong_expression": "Travel.",
        "why_wrong": "单说 travel 太短，容易显得不清楚。",
        "communication_intent": "说明自己是来旅游的",
        "answer_levels": [
            {
                "level": "survival",
                "label": "最短能救场",
                "english": "For vacation.",
                "chinese": "来度假。",
                "usage": "紧张时先接住问题。",
            },
            {
                "level": "standard",
                "label": "完整一点",
                "english": "I'm here for vacation.",
                "chinese": "我是来度假的。",
                "usage": "入境回答最稳。",
            },
            {
                "level": "polite",
                "label": "再补一句",
                "english": "I'll stay for seven days.",
                "chinese": "我会停留七天。",
                "usage": "对方继续问行程时用。",
            },
        ],
        "next_preview": "下集讲入境被问住哪里。",
        "interaction": "你最怕入境官问什么？评论区说说。",
    },
    {
        "id": "office_follow_up",
        "keywords": ["办公室催进度", "催进度", "进度", "跟进"],
        "scene": "office",
        "sub_scene": "follow_up",
        "topic": "办公室催进度",
        "real_scene": "你想问同事任务进展，但不想听起来像催命",
        "staff_line": "Do you need anything from me?",
        "staff_line_cn": "你需要我配合什么吗？",
        "pain_point": "催进度，别说 hurry up",
        "wrong_expression": "Please hurry up.",
        "why_wrong": "这句太冲，办公室里容易冒犯。",
        "communication_intent": "礼貌询问进展",
        "answer_levels": [
            {
                "level": "survival",
                "label": "最短能救场",
                "english": "Any update?",
                "chinese": "有进展吗？",
                "usage": "熟人之间快速问。",
            },
            {
                "level": "standard",
                "label": "完整一点",
                "english": "Do you have any updates on this?",
                "chinese": "这个有新进展吗？",
                "usage": "办公室沟通最常用。",
            },
            {
                "level": "polite",
                "label": "更礼貌一点",
                "english": "Just checking in on the progress.",
                "chinese": "我来跟进一下进度。",
                "usage": "邮件和聊天都自然。",
            },
        ],
        "next_preview": "下集讲会议里打断别人怎么说。",
        "interaction": "你还想学哪句办公室英语？评论区说说。",
    },
]


SCENE_COLLECTION_PRESETS: List[Dict[str, Any]] = [
    {
        "id": "plane_attendant_help",
        "keywords": [
            "飞机上找空乘", "飞机上找空姐", "找空乘", "找空姐",
            "飞机上求助", "飞机上寻求帮助", "飞机上寻求空乘帮助",
            "空乘帮忙", "空乘帮助", "寻求空乘帮助", "叫空乘帮忙", "找空乘帮忙",
        ],
        "scene": "travel",
        "sub_scene": "in_flight_attendant",
        "topic": "飞机上找空乘",
        "real_scene": "你在飞机上想找空乘帮忙，但一开口就卡住",
        "hook": "飞机上想找空乘，别只会 hello。",
        "setup": "这 5 句按顺序学，求助、放行李、要东西、报故障都能用。",
        "expressions": [
            {
                "label": "先开口求助",
                "english": "Excuse me, could you help me?",
                "chinese": "不好意思，可以帮我一下吗？",
                "usage": "不知道怎么开始时先用这句。",
            },
            {
                "label": "请人放行李",
                "english": "Could you help me put this up?",
                "chinese": "可以帮我把这个放上去吗？",
                "usage": "指着行李说 this 就够自然。",
            },
            {
                "label": "想要毯子",
                "english": "May I have a blanket?",
                "chinese": "可以给我一条毯子吗？",
                "usage": "要服务物品时很礼貌。",
            },
            {
                "label": "想要水",
                "english": "Could I have some water?",
                "chinese": "可以给我一些水吗？",
                "usage": "比 water please 更完整。",
            },
            {
                "label": "座位屏幕坏了",
                "english": "My seat screen isn't working.",
                "chinese": "我的座位屏幕不能用。",
                "usage": "报故障时直接说明哪里不能用。",
            },
        ],
        "summary_tts": "这 5 句先收藏，飞机上找空乘真的用得上。",
        "next_preview": "下集讲飞机上换座位怎么说。",
        "interaction": "你在飞机上还卡过哪句英语？评论区说说。",
        "title": "【飞机上找空乘】不会开口求助？这5句能救场",
    },
    {
        "id": "airport_checkin_collection",
        "keywords": ["机场值机", "值机", "机场柜台", "check in", "check-in"],
        "scene": "travel",
        "sub_scene": "airport_checkin",
        "topic": "机场值机",
        "real_scene": "你在机场值机柜台，需要办理登机和行李",
        "hook": "机场值机别慌，这 5 句按顺序说就够。",
        "setup": "从办理值机到确认登机口，一条视频学完整。",
        "expressions": [
            {
                "label": "办理值机",
                "english": "I'd like to check in for this flight.",
                "chinese": "我想办理这趟航班的值机。",
                "usage": "到柜台第一句可以这样开口。",
            },
            {
                "label": "托运行李",
                "english": "I have one bag to check.",
                "chinese": "我有一个包要托运。",
                "usage": "回答有没有托运行李。",
            },
            {
                "label": "确认随身行李",
                "english": "Is my carry-on okay?",
                "chinese": "我的随身行李可以吗？",
                "usage": "担心尺寸或重量时用。",
            },
            {
                "label": "想要靠窗",
                "english": "Could I have a window seat?",
                "chinese": "可以给我靠窗座位吗？",
                "usage": "选座时礼貌表达。",
            },
            {
                "label": "问登机口",
                "english": "Which gate should I go to?",
                "chinese": "我应该去哪个登机口？",
                "usage": "离开柜台前确认路线。",
            },
        ],
        "summary_tts": "这 5 句先收藏，机场值机一套就顺了。",
        "next_preview": "下集讲行李超重怎么说。",
        "interaction": "你值机时最怕被问什么？评论区说说。",
        "title": "【机场值机】不会办托运？这5句直接用",
    },
    {
        "id": "hotel_checkout_collection",
        "keywords": ["酒店退房", "退房", "check out", "checkout"],
        "scene": "hotel",
        "sub_scene": "hotel_checkout",
        "topic": "酒店退房",
        "real_scene": "你在酒店前台准备退房，需要确认账单和寄存行李",
        "hook": "酒店退房别只会 check out，这 5 句更完整。",
        "setup": "从退房、查账单到寄存行李，一次学会。",
        "expressions": [
            {
                "label": "我要退房",
                "english": "I'd like to check out, please.",
                "chinese": "我想办理退房。",
                "usage": "到前台第一句。",
            },
            {
                "label": "核对账单",
                "english": "Could you check the bill for me?",
                "chinese": "可以帮我核对一下账单吗？",
                "usage": "担心多收费时用。",
            },
            {
                "label": "指出多收费",
                "english": "I think there is an extra charge here.",
                "chinese": "我觉得这里多收了一项费用。",
                "usage": "发现问题时更具体。",
            },
            {
                "label": "寄存行李",
                "english": "Could I leave my luggage here for a few hours?",
                "chinese": "我可以把行李寄存在这里几个小时吗？",
                "usage": "退房后还要出去逛时用。",
            },
            {
                "label": "要收据",
                "english": "Could I have a receipt, please?",
                "chinese": "可以给我一张收据吗？",
                "usage": "商务或报销场景常用。",
            },
        ],
        "summary_tts": "这 5 句先收藏，退房查账单都能用。",
        "next_preview": "下集讲押金没退怎么说。",
        "interaction": "你退房时遇到过什么尴尬？评论区说说。",
        "title": "【酒店退房】怕账单多收费？这5句要会",
    },
]


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
            if preset else build_fallback_scene_collection(clean_topic)
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
        if len(expressions) < 4:
            issues.append("场景式内容少于 4 句，收藏价值偏弱。")
            suggestions.append("补足到同一场景下 4-5 个连续动作。")
        if len(expressions) > 5:
            issues.append("场景式内容超过 5 句，容易拖慢完播。")
            suggestions.append("只保留同一场景里最刚需的 5 句。")
        if _looks_cross_scene(brief):
            issues.append("句子疑似跨了多个场景。")
            suggestions.append("拆成多条视频，单条只讲一个具体场景。")
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
    if scene == "business":
        return {"voice": "business", "speed": 1.08, "style": "professional_clear"}
    if scene == "parent_child":
        return {"voice": "cute", "speed": 1.05, "style": "warm_parent_child"}
    if content_mode == "scene_collection":
        return {"voice": "playful", "speed": 1.10, "style": "bright_companion"}
    if content_mode == "painpoint_contrast":
        return {"voice": "playful", "speed": 1.12, "style": "snappy_contrast"}
    return {"voice": "vivi", "speed": 1.08, "style": "clear_bilingual"}


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
    scene_map = [
        ("emergency", ["救场", "卡壳", "听不清", "不会说", "付款失败", "迷路", "丢东西"]),
        ("hotel", ["酒店", "入住", "退房", "房间", "前台", "押金", "早餐"]),
        ("office", ["办公室", "开会", "请假", "催进度", "汇报", "同事", "进度"]),
        ("business", ["商务", "客户", "合同", "谈判", "报价", "提案"]),
        ("parent_child", ["亲子", "孩子", "绘本", "睡前"]),
        ("daily", ["日常", "生活", "咖啡", "外卖", "超市", "理发"]),
        ("travel", ["旅行", "机场", "入境", "航班", "行李", "登机", "护照", "值机"]),
    ]
    for scene, keywords in scene_map:
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


def build_fallback_scene_collection(topic: str) -> Dict[str, Any]:
    scene = detect_scene(topic)
    return {
        "id": slugify_topic(topic),
        "scene": scene,
        "sub_scene": slugify_topic(topic),
        "topic": topic,
        "real_scene": f"{topic}这个具体场景里，先学最容易用上的几句。",
        "hook": f"{topic}别硬憋英文，这 5 句先收藏。",
        "setup": "先按真实对话顺序学，开口、说明需求、确认信息都覆盖。",
        "expressions": [
            {
                "label": "先开口",
                "english": "Excuse me, could you help me?",
                "chinese": "不好意思，可以帮我一下吗？",
                "usage": "不知道怎么开始时先用。",
            },
            {
                "label": "说明需求",
                "english": "I'd like to ask about this.",
                "chinese": "我想问一下这个。",
                "usage": "把问题递给对方。",
            },
            {
                "label": "确认信息",
                "english": "Could you confirm that for me?",
                "chinese": "可以帮我确认一下吗？",
                "usage": "听到信息后再核对。",
            },
            {
                "label": "没听清",
                "english": "Could you say that again?",
                "chinese": "可以再说一遍吗？",
                "usage": "没听清时别硬猜。",
            },
            {
                "label": "表达感谢",
                "english": "Thanks, that helps a lot.",
                "chinese": "谢谢，这帮了我很多。",
                "usage": "结束沟通时自然收尾。",
            },
        ],
        "summary_tts": f"这 5 句先收藏，{topic}时可以直接用。",
        "next_preview": f"下集继续讲{topic}里的高频卡壳句。",
        "interaction": f"你在{topic}还卡过哪句？评论区说说。",
        "title": f"【{topic[:8]}】不会开口？这5句能救场",
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
