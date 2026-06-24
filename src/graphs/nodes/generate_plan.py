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

## 核心规则（必须严格遵守）

### 1. 视频结构（固定7个片段）
- 标题页（1个）
- 英语跟读句子（固定5个）
- 结尾汇总复习页（1个）

### 2. 视频时长
- 目标：40-60秒
- 每个跟读句子含音频约5-8秒
- 标题页约2秒
- 结尾页约6-8秒

### 3. TTS 文案格式（每个跟读句子必须严格按此格式）
第N句。
英文句子。
中文意思。
跟我读：英文句子。
再来一遍：英文句子。

示例：
第1句。
I have a reservation under the name Wang.
我在王先生名下预订了房间。
跟我读：I have a reservation under the name Wang.
再来一遍：I have a reservation under the name Wang.

### 4. 字幕规则
- 位置：顶部15%-25%区域
- 格式：两行，英文在上，中文在下
- 颜色：深色文字#111111
- 背景：白色半透明底板
- 不要遮挡小丸子的脸、眼睛、身体

### 5. 图片提示词规则
- 顶部25%区域：保持干净、少元素、无文字
- 主体（小丸子和关键物体）：放在画面中下部分
- 不要生成任何文字内容
- 所有文字通过剪映字幕层叠加
- 主角固定为"小丸子"
- 场景根据主题选择，不要默认通勤

### 6. 结尾汇总复习页
- 图片背景：干净简洁的复习卡背景
- 示例：小丸子站在空白复习清单旁边，画面无文字，中心留白较多
- 字幕内容：今日5句跟读复习 + 5行1.英文-中文格式
- 字幕位置：中上区域，不要遮挡小丸子

### 7. 场景选择规则
- 亲子启蒙：家庭/绘本/玩具场景
- 商务英语：办公室/会议/电脑场景
- 旅行英语：酒店/机场/餐厅/景点场景
- 日常口语：生活服务/朋友聊天/咖啡店场景
- 不要默认通勤/地铁/公交场景

### 8. 主角形象
- 统一使用：极简卡通圆头豆豆人"小丸子"
- 浅色背景，黑色简洁线条
- 少细节，竖屏9:16
- 保持形象一致

## 输出 JSON 格式（严格遵循7个片段）

{{
    "content_meta": {{
        "selected_topic": "基于用户输入的主题",
        "scene": "{scene}",
        "duration_seconds": <总时长>,
        "originality_check": "内容处理说明",
        "safety_note": "如涉及教材/真题，说明未复述原文"
    }},
    "publish_pack": {{
        "title": "短视频标题",
        "cover_text": "封面文案",
        "description": "发布文案",
        "hashtags": ["英语学习", "每日英语"]
    }},
    "review_card": {{
        "today_expressions": [
            {{
                "english": "英文句子",
                "chinese": "中文意思",
                "usage": "使用场景"
            }}
        ],
        "quick_review": "复盘提醒"
    }},
    "segments": [
        {{
            "scene": "标题页",
            "caption": "英文标题\\n中文副标题",
            "tts": "标题配音文本，控制在2秒内",
            "image_prompt": "简洁场景图，顶部25%空白，主体在中下部分",
            "duration": 2.0
        }},
        {{
            "scene": "第1句",
            "caption": "英文句子\\n中文意思",
            "tts": "第1句。英文句子。中文字意思。跟我读：英文句子。再来一遍：英文句子。",
            "image_prompt": "根据英文句子语义设计场景，小丸子做对应动作/表情",
            "duration": 6.0
        }},
        {{
            "scene": "第2句",
            "caption": "英文句子\\n中文意思",
            "tts": "第2句。英文句子。中文字意思。跟我读：英文句子。再来一遍：英文句子。",
            "image_prompt": "根据英文句子语义设计场景，小丸子做对应动作/表情",
            "duration": 6.0
        }},
        {{
            "scene": "第3句",
            "caption": "英文句子\\n中文意思",
            "tts": "第3句。英文句子。中文字意思。跟我读：英文句子。再来一遍：英文句子。",
            "image_prompt": "根据英文句子语义设计场景，小丸子做对应动作/表情",
            "duration": 6.0
        }},
        {{
            "scene": "第4句",
            "caption": "英文句子\\n中文意思",
            "tts": "第4句。英文句子。中文字意思。跟我读：英文句子。再来一遍：英文句子。",
            "image_prompt": "根据英文句子语义设计场景，小丸子做对应动作/表情",
            "duration": 6.0
        }},
        {{
            "scene": "第5句",
            "caption": "英文句子\\n中文意思",
            "tts": "第5句。英文句子。中文字意思。跟我读：英文句子。再来一遍：英文句子。",
            "image_prompt": "根据英文句子语义设计场景，小丸子做对应动作/表情",
            "duration": 6.0
        }},
        {{
            "scene": "结尾复习页",
            "caption": "今日5句跟读复习\\n1. 英文1 - 中文1\\n2. 英文2 - 中文2\\n3. 英文3 - 中文3\\n4. 英文4 - 中文4\\n5. 英文5 - 中文5",
            "tts": "来复习一下今天学的5句话。第一句，英文1。第二句，英文2。第三句，英文3。第四句，英文4。第五句，英文5。",
            "image_prompt": "干净简洁的复习卡背景，小丸子站在旁边，画面无文字，中心留白较多",
            "duration": 8.0
        }}
    ],
    "material_bank": []
}}

## 重要说明
1. segments 必须固定7个片段：标题页 + 5个跟读句 + 结尾复习页
2. 每个跟读句子的 tts 必须使用上面规定的格式
3. image_prompt 必须与该片段英文句子语义严格匹配
4. 图片顶部25%保持空白，所有文字通过字幕叠加
5. 结尾页图片不要有文字，内容全部用字幕层
6. 输出纯 JSON，不要有任何额外文字"""

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
