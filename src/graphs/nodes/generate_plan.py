"""
通勤英语内容生成节点
输入: learning_note, scene, duration_seconds, audience, tone, canvas_width, canvas_height
输出: content_meta, publish_pack, voice_text, review_card, video_plan, material_bank, segments
"""
import json
import logging
from typing import Dict, Any, List
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

    # 场景映射
    scene_mapping = {
        "commute": "早晚通勤",
        "parent_child": "亲子绘本",
        "travel": "生活旅游",
        "business": "商务英语",
        "bec": "BEC备考"
    }
    scene_name = scene_mapping.get(scene, "通勤学习")

    # 构建 prompt，生成结构化片段数据
    prompt = f"""你是「通勤英语内容助手」，帮助英语学习者把每日学习笔记转化为原创短视频内容。

## 用户输入
- 学习笔记: {learning_note}
- 场景: {scene_name}
- 目标受众: {audience}
- 风格: {tone}

## 核心任务
为每个片段生成结构化数据，包括：
1. scene: 场景名称
2. caption: 字幕（英文在上，中文在下，用\\n分隔）
3. tts: TTS配音文本
4. image_prompt: 图片生成提示词
5. duration: 预估时长（秒）

## 内容生成规则

### 原创性要求
1. 内容必须原创，不得搬运教材、课程、真题、绘本原文
2. 英文例句必须是重新组织的原创表达
3. 如果涉及 BEC，只能生成风格练习、商务表达和备考建议，不解析真题原文

### 视频结构
总时长控制在 25-35 秒：
- 开头 1.5 秒：标题页（显示视频主题）
- 每个表达约 4-6 秒（包含画面+字幕+配音）
- 结尾 2-3 秒：复习页（列出所有表达）

### 每条表达的结构
每个表达都要包含：
1. 场景画面（与英文句子语义完全匹配）
2. 字幕（英文在上，中文在下）
3. TTS配音文本

### 画面匹配规则
- 画面必须和英文句子语义完全匹配
- 例如 "rush hour traffic"：画面应该是堵车、早高峰、通勤车辆
- 不要生成 Excuse me / Thank you / Sorry / You're welcome 这种无关内容

### 图片风格要求
极简卡通火柴人插画：
- 白色或浅色背景
- 黑色线条
- 少细节
- 主体明确
- 表情夸张可爱
- 竖屏 9:16
- 主体占画面 55%-70%
- 图片底部预留 25% 空白区域给字幕

### 字幕排版规则
- 固定放在画面底部安全区
- 不要遮挡人物脸、身体、车辆等主体
- 英文在上，中文在下，最多两行
- 字幕太长时要改短，不要强行塞满

### 结尾复习页规则
- 复习本视频所有英文表达
- 格式：把之前所有英文句子列出

## 输出 JSON 格式

{{
    "content_meta": {{
        "selected_topic": "今日主视频主题",
        "scene": "{scene}",
        "duration_seconds": <总时长>,
        "originality_check": "说明内容是如何原创改写的",
        "safety_note": "如果涉及BEC/绘本/教材，说明未复述原文"
    }},
    "publish_pack": {{
        "title": "短视频标题（吸引人）",
        "cover_text": "封面文案，最多两行",
        "description": "发布文案",
        "hashtags": ["通勤英语", "英语学习", "每日英语"]
    }},
    "review_card": {{
        "today_expressions": [
            {{
                "english": "英文表达",
                "chinese": "中文翻译",
                "usage": "使用场景"
            }}
        ],
        "quick_review": "复盘提醒"
    }},
    "segments": [
        {{
            "scene": "标题",
            "caption": "字幕文字\\n中文翻译",
            "tts": "TTS配音文本",
            "image_prompt": "极简卡通火柴人插画，白色背景...（详细描述）",
            "duration": 1.5
        }},
        {{
            "scene": "表达1",
            "caption": "I missed the subway train!\\n我错过地铁了！",
            "tts": "I missed the subway train. 我错过地铁了。",
            "image_prompt": "极简卡通火柴人插画，白色背景，黑色线条，火柴人蹲在地铁车门旁拍大腿，表情懊恼，地铁已经开走，竖屏9:16，主体占60%",
            "duration": 4.0
        }}
    ],
    "material_bank": [
        {{
            "topic": "备用素材点",
            "reason": "为什么今天不作为主视频"
        }}
    ]
}}

## 重要说明
1. 每个 segment 必须包含 scene, caption, tts, image_prompt, duration
2. 总时长 = 所有 segment.duration 之和，控制在 25-35 秒
3. 所有英文句子必须是原创，不能照搬教材
4. 输出纯 JSON，不要有任何额外文字"""

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

        # 构建 video_plan 和 segments
        segments = result.get("segments", [])
        
        # 计算时间轴（基于实际的 TTS 时长，但先用预估时长）
        current_time = 0
        video_scenes = []
        video_captions = []
        
        for seg in segments:
            duration = seg.get("duration", 4.0)
            start_us = int(current_time * 1000000)
            end_us = int((current_time + duration) * 1000000)
            
            video_scenes.append({
                "start": start_us,
                "end": end_us,
                "type": "image",
                "visual_role": seg.get("scene", "scene"),
                "prompt": seg.get("image_prompt", "")
            })
            
            video_captions.append({
                "start": start_us,
                "end": end_us,
                "text": seg.get("caption", "")
            })
            
            current_time += duration
        
        total_duration = int(current_time * 1000000)
        
        # 构建 voice_text（拼接所有 TTS 文本）
        voice_text = " ".join([seg.get("tts", "") for seg in segments])

        video_plan = {
            "canvas": {
                "width": canvas_width,
                "height": canvas_height
            },
            "duration": total_duration,
            "scenes": video_scenes,
            "captions": video_captions
        }

        logger.info(f"Generated content plan: {result.get('content_meta', {}).get('selected_topic', 'unknown')}, total_duration: {current_time:.1f}s, segments: {len(segments)}")

        return {
            "content_meta": result.get("content_meta"),
            "publish_pack": result.get("publish_pack"),
            "voice_text": voice_text,
            "review_card": result.get("review_card"),
            "video_plan": video_plan,
            "material_bank": result.get("material_bank", []),
            "segments": segments,
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
            "segments": None,
            "error": f"生成内容计划失败: {str(e)}"
        }
