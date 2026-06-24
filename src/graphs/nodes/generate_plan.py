"""
通勤英语内容生成节点
输入: learning_note, scene, duration_seconds, audience, tone, canvas_width, canvas_height
输出: content_meta, publish_pack, voice_text, review_card, video_plan, material_bank
"""
import json
import logging
from typing import Dict, Any
from coze_coding_dev_sdk import LLMClient
from coze_coding_utils.runtime_ctx.context import new_context
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


def generate_plan(state: Dict[str, Any]) -> Dict[str, Any]:
    """生成通勤英语短视频内容计划"""
    ctx = new_context(method="generate_plan")
    client = LLMClient(ctx=ctx)

    # 解析输入
    learning_note = state.get("learning_note", "")
    scene = state.get("scene", "commute")
    duration_seconds = state.get("duration_seconds", 60)
    audience = state.get("audience", "英语学习者")
    tone = state.get("tone", "轻松实用")
    canvas_width = state.get("canvas_width", 1080)
    canvas_height = state.get("canvas_height", 1920)

    # 确保时长在 25-35 秒范围内
    duration_seconds = max(25, min(35, duration_seconds))
    duration_microseconds = duration_seconds * 1000000

    # 场景映射
    scene_mapping = {
        "commute": "早晚通勤",
        "parent_child": "亲子绘本",
        "travel": "生活旅游",
        "business": "商务英语",
        "bec": "BEC备考"
    }

    scene_name = scene_mapping.get(scene, "通勤学习")

    # 构建 prompt
    prompt = f"""你是「通勤英语内容助手」，专门帮助英语学习者把每日学习笔记转化为原创短视频内容。

## 用户输入
- 学习笔记: {learning_note}
- 场景: {scene_name}
- 目标受众: {audience}
- 风格: {tone}
- 视频时长: {duration_seconds}秒

## 内容生成规则（必须严格遵守）

### 原创性要求
1. 内容必须原创，不得搬运教材、课程、真题、绘本原文
2. 如果涉及 BEC，只能生成风格练习、商务表达和备考建议，不解析真题原文
3. 如果涉及绘本，只生成围绕主题的亲子互动句，不复述绘本原文
4. 英文例句必须是重新组织的原创表达

### 视频结构要求
总时长 {duration_seconds} 秒，节奏分配：
- 开头 2 秒：标题页，吸引眼球
- 每个表达 5-6 秒：先显示场景图，同时显示英文句子和中文翻译
- 结尾 3 秒：复习前面出现的所有英文表达

### 每条表达的结构（每个表达都是这个结构）
1. 场景画面（与英文句子语义完全匹配）
2. 画面上同时显示英文句子和中文翻译（不要拆成英文一页、中文一页）

### 画面匹配规则
- 画面必须和英文句子语义完全匹配
- 例如 "rush hour traffic"：画面应该是堵车、早高峰、通勤车辆，不要出现咖啡机
- 例如 "shuttle bus"：画面应该是赶班车的人和通勤班车
- 例如 "packed like sardines"：画面应该是拥挤地铁
- 不要生成 Excuse me / Thank you / Sorry / You're welcome 这种无关内容

### 图片风格要求
极简卡通火柴人插画：
- 白色或浅色背景
- 黑色线条
- 少细节
- 主体明确
- 表情夸张可爱
- 竖屏 9:16
- 主体占画面 55%-70%，不要大面积空白

### 字幕排版规则
- 字幕放在画面底部安全区
- 不要遮挡人物脸、身体、车辆、地铁等主体
- 最多两行：英文在上，中文在下
- 字号要足够大，移动端能看清
- 不要把字幕放在画面正中间

### 结尾复习页规则
- 必须复习本视频出现过的所有英文表达
- 不要换成其他日常短句
- 不要生成 Excuse me / Thank you / Sorry / You're welcome

## 输出 JSON 格式（严格遵循）

{{
    "content_meta": {{
        "selected_topic": "今日主视频主题",
        "scene": "{scene}",
        "duration_seconds": {duration_seconds},
        "originality_check": "说明内容是如何原创改写的",
        "safety_note": "如果涉及BEC/绘本/教材，说明未复述原文"
    }},
    "publish_pack": {{
        "title": "短视频标题（吸引人）",
        "cover_text": "封面文案，最多两行",
        "description": "发布文案（带引导语）",
        "hashtags": ["通勤英语", "英语学习", "每日英语"]
    }},
    "voice_text": "完整原创口播文案（{duration_seconds}秒左右，与画面节奏匹配）",
    "review_card": {{
        "today_expressions": [
            {{
                "english": "英文表达1",
                "chinese": "中文翻译",
                "usage": "使用场景"
            }}
        ],
        "quick_review": "复盘提醒"
    }},
    "video_plan": {{
        "canvas": {{
            "width": {canvas_width},
            "height": {canvas_height}
        }},
        "duration": {duration_microseconds},
        "scenes": [
            {{
                "start": 0,
                "end": 2000000,
                "type": "image",
                "visual_role": "hook",
                "prompt": "极简卡通火柴人插画，白色背景，黑色线条，人物表情夸张可爱，竖屏9:16。开场标题画面"
            }}
        ],
        "captions": [
            {{
                "start": 0,
                "end": 2000000,
                "text": "标题文字"
            }}
        ]
    }},
    "material_bank": [
        {{
            "topic": "未入选但可之后使用的素材点",
            "reason": "为什么今天不作为主视频"
        }}
    ]
}}

## 重要说明
- video_plan 的 scenes 和 captions 时间必须覆盖整个 {duration_seconds} 秒
- 每个表达的画面必须和对应的英文句子语义完全匹配
- 结尾复习页必须列出本视频所有英文表达
- 所有时间使用微秒（1秒=1000000微秒）
- 必须输出纯 JSON，不要有任何额外文字"""

    messages = [
        SystemMessage(content="你是专业的通勤英语内容策划专家，擅长生成原创短视频脚本。"),
        HumanMessage(content=prompt)
    ]

    try:
        response = client.invoke(
            messages=messages,
            temperature=0.7,
            max_completion_tokens=12000
        )

        # 提取 JSON
        content = response.content
        if isinstance(content, list):
            if content and isinstance(content[0], dict):
                content = content[0].get("text", "")
            elif content:
                content = str(content[0])
            else:
                content = ""
        elif not isinstance(content, str):
            content = str(content)

        # 查找 JSON 块
        json_start = content.find('{')
        json_end = content.rfind('}') + 1

        if json_start != -1 and json_end > json_start:
            json_str = content[json_start:json_end]
            result = json.loads(json_str)
        else:
            raise ValueError("无法从响应中提取 JSON")

        logger.info(f"Generated content plan: {result.get('content_meta', {}).get('selected_topic', 'unknown')}")

        return {
            "content_meta": result.get("content_meta"),
            "publish_pack": result.get("publish_pack"),
            "voice_text": result.get("voice_text"),
            "review_card": result.get("review_card"),
            "video_plan": result.get("video_plan"),
            "material_bank": result.get("material_bank", []),
            "error": None
        }

    except Exception as e:
        logger.error(f"Error generating plan: {e}")
        return {
            "content_meta": None,
            "publish_pack": None,
            "voice_text": None,
            "review_card": None,
            "video_plan": None,
            "material_bank": None,
            "error": f"生成内容计划失败: {str(e)}"
        }
