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
        "interaction": "你在机场还卡过哪句？评论区打机场。",
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
        "interaction": "你退房时遇到过账单问题吗？评论区打酒店。",
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
        "interaction": "你住酒店最怕什么问题？评论区打酒店。",
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
        "interaction": "你最怕入境官问什么？评论区打入境。",
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
        "interaction": "你还想学哪句办公室英语？评论区打办公。",
    },
]


def parse_topic_input(raw_text: str) -> Dict[str, Any]:
    """Parse a user-supplied short topic into routing metadata."""
    topic = (raw_text or "").strip()
    preset = find_topic_preset(topic)
    return {
        "raw_topic": topic,
        "topic": preset.get("topic") if preset else topic,
        "scene": preset.get("scene") if preset else detect_scene(topic),
        "sub_scene": preset.get("sub_scene") if preset else slugify_topic(topic),
        "content_mode": "hybrid",
        "primary_mode": "painpoint_contrast",
        "secondary_mode": "immersive_follow_read",
        "ending_mode": "checkin_challenge",
        "auto_generate_expressions": True,
    }


def build_topic_brief(raw_topic: str, memory_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Build a concrete one-video brief from a broad topic."""
    memory_context = memory_context or {}
    preset = select_topic_preset(raw_topic, memory_context)
    if preset:
        brief = {k: v for k, v in preset.items() if k != "keywords"}
    else:
        topic = (raw_topic or "真实场景英语").strip()
        brief = build_fallback_brief(topic)

    brief["raw_topic"] = raw_topic
    brief["topic_id"] = generate_topic_id(brief.get("topic", raw_topic), brief.get("scene", "travel"))
    brief["content_mode"] = "hybrid"
    return brief


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
            "tts": f"现在你在{brief.get('real_scene', '真实场景里')}。对方问：{brief.get('staff_line', '')}",
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
    return [
        item.get("english", "").strip()
        for item in brief.get("answer_levels", [])
        if item.get("english")
    ]


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
        "real_scene": f"{topic}这个真实场景里，你突然不知道怎么接话",
        "staff_line": "How can I help you?",
        "staff_line_cn": "有什么可以帮你？",
        "pain_point": f"{topic}时，别只会说 yes",
        "wrong_expression": "Yes.",
        "why_wrong": "只说 yes 信息太少，对方不知道你具体要什么。",
        "communication_intent": f"在{topic}场景里把话接住",
        "answer_levels": [
            {
                "level": "survival",
                "label": "最短能救场",
                "english": "Yes, please.",
                "chinese": "好的，麻烦了。",
                "usage": "先礼貌接住。",
            },
            {
                "level": "standard",
                "label": "完整一点",
                "english": "Could you help me with this?",
                "chinese": "可以帮我处理一下这个吗？",
                "usage": "不确定怎么说时很万能。",
            },
            {
                "level": "polite",
                "label": "更礼貌一点",
                "english": "Could you please take a look at this?",
                "chinese": "可以麻烦你看一下这个吗？",
                "usage": "需要对方帮忙查看时用。",
            },
        ],
        "next_preview": f"下集继续讲{topic}里的卡壳表达。",
        "interaction": f"你在{topic}还卡过哪句？评论区告诉我。",
    }


def sanitize_tts(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"再来一遍[:：]?.*$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


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
