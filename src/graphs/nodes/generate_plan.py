"""
英语短视频内容生成节点
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
    """根据用户输入生成英语短视频内容计划"""
    ctx = new_context(method="generate_plan")
    client = LLMClient(ctx=ctx)

    # 解析输入
    learning_note = state.get("learning_note") or state.get("topic") or state.get("text") or ""
    scene = state.get("scene") or state.get("style") or "general"
    duration_seconds = state.get("duration_seconds", 60)
    audience = state.get("audience", "英语学习者")
    tone = state.get("tone", "轻松实用")
    canvas_width = state.get("canvas_width", 1080)
    canvas_height = state.get("canvas_height", 1920)

    # 场景映射
    scene_mapping = {
        "general": "碎片时间英语",
        "daily": "日常口语",
        "parent_child": "亲子绘本",
        "travel": "生活旅游",
        "business": "商务英语",
        "office": "办公室英语",
        "bec": "BEC备考",
        "commute": "通勤场景"
    }
    scene_name = scene_mapping.get(scene, scene if scene else "碎片时间英语")

    # 构建 prompt，根据用户输入决定场景
    prompt = f"""你是「英语短视频内容助手」，严格根据用户提供的学习笔记或主题生成内容。

## 用户输入（直接使用，禁止改变）
学习笔记: {learning_note}

## 核心原则
1. **禁止**：添加用户未提供的内容
2. **禁止**：改变用户指定的主题方向
3. **必须**：直接使用用户提供的英文表达或其同义改写
4. **必须**：根据用户主题选择合适的场景画面
5. **必须**：固定主角是“小丸子”，她是利用碎片时间学英语的年轻打工人学习搭子
6. **必须**：每个图片 prompt 都写明底部预留字幕区域，不遮挡人物脸、身体、手机和关键物体
7. **必须**：英文和中文同屏，英文在上、中文在下，字幕最多两行
8. **禁止**：除非用户主题明确要求通勤/地铁/公交/堵车，否则不要默认生成通勤场景

## 输出 JSON 格式（严格遵循）

{{
    "content_meta": {{
        "selected_topic": "{learning_note[:50]}...",
        "scene": "{scene}",
        "duration_seconds": <总时长>,
        "originality_check": "内容处理说明",
        "safety_note": "如涉及教材/真题，说明未复述原文"
    }},
    "publish_pack": {{
        "title": "基于用户主题的短视频标题",
        "cover_text": "封面文案",
        "description": "基于用户输入的发布文案",
        "hashtags": ["英语学习", "每日英语"]
    }},
    "review_card": {{
        "today_expressions": [
            {{
                "english": "用户提供的或同义改写的英文表达",
                "chinese": "对应的中文翻译",
                "usage": "使用场景说明"
            }}
        ],
        "quick_review": "复盘提醒"
    }},
    "segments": [
        {{
            "scene": "标题页",
            "caption": "英文标题\\n中文副标题",
            "tts": "标题配音文本",
            "image_prompt": "根据用户主题设计场景",
            "duration": 1.5
        }}
    ],
    "material_bank": []
}}

## 重要说明
1. segments 必须生成 4 个片段：标题页 + 3 个英语表达，不要生成无音频的长结尾页
2. 每个表达片段必须使用用户提供的英文表达或主题下最相关的表达
3. image_prompt 必须与该片段英文句子语义严格匹配
4. image_prompt 必须根据用户主题选择场景：亲子启蒙用家庭/绘本/玩具，商务英语用办公室/会议/电脑，旅行英语用酒店/机场/餐厅/问路，日常口语用生活服务/朋友聊天/咖啡店/便利店。不要默认通勤场景
5. image_prompt 统一使用：极简卡通圆头豆豆人“小丸子”，浅色背景，黑色简洁线条，少细节，竖屏9:16，底部预留 25% 字幕区域
6. caption 必须是两行：英文句子\\n中文意思
7. tts 必须朗读该片段 caption 对应内容，不能为空
8. 每个表达的 tts 控制在 3-5 秒，标题页 tts 控制在 1-2 秒
9. 输出纯 JSON，不要有任何额外文字"""

    messages = [
        SystemMessage(content="你是专业的英语短视频内容策划专家，擅长根据用户输入生成原创短视频脚本。严格遵循用户提供的主题，不添加无关内容。"),
        HumanMessage(content=prompt)
    ]

    try:
        response = client.invoke(
            messages=messages,
            temperature=0.7,
            max_completion_tokens=12000
        )

        # 提取 JSON
        content = response.content if response else ""
        if isinstance(content, list):
            if content and isinstance(content[0], dict):
                content = content[0].get("text", "")
            elif content:
                content = str(content[0])
            else:
                content = ""
        elif not isinstance(content, str):
            content = str(content) if content else ""

        if not content:
            raise ValueError("LLM 返回内容为空")

        # 查找 JSON 块
        json_start = content.find('{')
        json_end = content.rfind('}') + 1

        if json_start != -1 and json_end > json_start:
            json_str = content[json_start:json_end]
            result = json.loads(json_str)
        else:
            raise ValueError(f"无法从响应中提取 JSON。响应内容: {content[:500]}")

        # 验证 result 是有效的字典
        if not isinstance(result, dict):
            raise ValueError(f"LLM 返回的不是有效的 JSON 对象: {type(result)}")
        
        # 验证必要字段
        if "segments" not in result or not result["segments"]:
            raise ValueError(f"LLM 返回的 JSON 缺少 segments 字段或为空: {result.keys()}")

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
            "content_meta": result.get("content_meta") or {},
            "publish_pack": result.get("publish_pack") or {},
            "voice_text": voice_text or "",
            "review_card": result.get("review_card") or {},
            "video_plan": video_plan or {},
            "material_bank": result.get("material_bank") or [],
            "segments": segments or [],
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
