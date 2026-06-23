"""
生成视频计划节点
输入: topic, duration_seconds, style, canvas_width, canvas_height
输出: video_plan JSON
"""
import json
import logging
from typing import Dict, Any
from coze_coding_dev_sdk import LLMClient
from coze_coding_utils.runtime_ctx.context import new_context
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

CAPCUT_MATE_BASE_URL = "http://your-server-ip:30000/openapi/capcut-mate/v1"


def generate_plan(state: Dict[str, Any]) -> Dict[str, Any]:
    """生成视频计划 JSON"""
    ctx = new_context(method="generate_plan")
    client = LLMClient(ctx=ctx)
    
    topic = state.get("topic", "")
    duration_seconds = state.get("duration_seconds", 60)
    style = state.get("style", "小红书口播")
    canvas_width = state.get("canvas_width", 1080)
    canvas_height = state.get("canvas_height", 1920)
    
    duration_microseconds = duration_seconds * 1000000
    
    # 构建 prompt
    prompt = f"""请为以下短视频主题生成完整的视频制作计划：

主题: {topic}
时长: {duration_seconds} 秒
风格: {style}
画布尺寸: {canvas_width}x{canvas_height}

请按以下 JSON 格式输出（必须严格遵循此格式，所有时间使用微秒，1秒=1000000微秒）：

{{
    "canvas": {{
        "width": {canvas_width},
        "height": {canvas_height}
    }},
    "duration": {duration_microseconds},
    "voice_text": "完整口播文案（中文，{duration_seconds}秒左右）",
    "scenes": [
        {{
            "start": 0,
            "end": 8000000,
            "type": "image",
            "prompt": "英文 AI 画面提示词，9:16 vertical frame"
        }}
    ],
    "captions": [
        {{
            "start": 0,
            "end": 5000000,
            "text": "字幕文本"
        }}
    ]
}}

要求：
1. voice_text 是完整的口播文案，约 {duration_seconds} 秒朗读长度
2. scenes 数量建议 3-8 个，每个 scene 时长 5-10 秒
3. 每个 scene 的 prompt 是英文 AI 画面描述词，用于生成 9:16 竖屏图片
4. captions 的 text 要从 voice_text 中提取关键句子
5. 确保 scenes 和 captions 的时间覆盖整个视频时长
6. 必须输出纯 JSON，不要有任何额外文字"""

    messages = [
        SystemMessage(content="你是专业的短视频策划专家。"),
        HumanMessage(content=prompt)
    ]
    
    try:
        response = client.invoke(
            messages=messages,
            temperature=0.7,
            max_completion_tokens=8000
        )
        
        # 提取 JSON
        content = response.content
        if isinstance(content, list):
            # 处理列表格式的响应
            if content and isinstance(content[0], dict):
                # 从字典中提取 text
                content = content[0].get("text", "")
            elif content:
                content = str(content[0])
            else:
                content = ""
        elif not isinstance(content, str):
            content = str(content)
        
        # 尝试解析 JSON
        # 查找 JSON 块
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            json_str = content[json_start:json_end]
            video_plan = json.loads(json_str)
        else:
            raise ValueError("无法从响应中提取 JSON")
        
        logger.info(f"Generated video plan with {len(video_plan.get('scenes', []))} scenes")
        
        return {
            "video_plan": video_plan,
            "error": None
        }
        
    except Exception as e:
        logger.error(f"Error generating plan: {e}")
        return {
            "video_plan": None,
            "error": f"生成视频计划失败: {str(e)}"
        }
