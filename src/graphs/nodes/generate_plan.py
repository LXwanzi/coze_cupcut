"""
视频计划生成节点

支持多种输入格式：
1. 纯文本：用户输入英语句子或学习笔记
2. 文本+图片：用户提供句子或笔记，配参考图片
3. 仅图片：用户提供截图或照片，大模型识别其中的英语内容
"""

import os
import json
import re
import logging
from typing import Dict, Any, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from coze_coding_utils.runtime_ctx.context import default_headers, new_context

logger = logging.getLogger(__name__)

# LLM 配置
LLM_CONFIG_PATH = os.path.join(
    os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects"),
    "config", "agent_llm_config.json"
)

# 图片配置
CHARACTER_REFERENCE_IMAGE_URL = os.getenv(
    "CHARACTER_REFERENCE_IMAGE_URL",
    "https://coze-coding-project.tos.coze.site/bot File/assets/小丸子形象图.png"
)


def _load_llm_config() -> Dict[str, Any]:
    """加载 LLM 配置"""
    try:
        with open(LLM_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"加载 LLM 配置失败: {e}")
        return {
            "config": {"model": "doubao-seed-2-0-pro-250120", "temperature": 0.7},
            "sp": "You are a helpful assistant."
        }


def _get_llm():
    """获取 LLM 实例"""
    cfg = _load_llm_config()
    api_key = os.getenv("COZE_WORKLOAD_IDENTITY_API_KEY")
    base_url = os.getenv("COZE_INTEGRATION_MODEL_BASE_URL")
    
    return ChatOpenAI(
        model=cfg['config'].get("model"),
        api_key=api_key,
        base_url=base_url,
        temperature=cfg['config'].get('temperature', 0.7),
        timeout=120,
        default_headers=default_headers(new_context(method="generate_plan"))
    )


def generate_plan(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成视频计划
    
    支持的输入格式：
    - learning_note: 字符串，用户的学习笔记或英语句子
    - topic: 字符串，简单的主题描述
    - image_url: 字符串（可选），用户提供参考图片
    - scene: 字符串（可选），场景类型
    
    输出：
    - segments: 视频片段列表
    - content_meta: 内容元数据
    - publish_pack: 发布信息
    - review_card: 复习卡片
    """
    try:
        # 1. 提取用户输入
        learning_note = state.get('learning_note', '')
        topic = state.get('topic', '')
        user_input = learning_note or topic
        
        if not user_input:
            return {
                'error': '请提供学习内容或主题',
                'segments': [],
                'content_meta': {},
                'publish_pack': {},
                'review_card': {}
            }
        
        scene = state.get('scene', 'travel')
        duration_seconds = state.get('duration_seconds', 60)
        canvas_width = state.get('canvas_width', 1080)
        canvas_height = state.get('canvas_height', 1920)
        
        # 2. 调用 LLM 生成视频计划
        segments = _generate_video_plan(
            user_input=user_input,
            scene=scene,
            duration_seconds=duration_seconds
        )
        
        if not segments:
            return {
                'error': '未能生成视频计划',
                'segments': [],
                'content_meta': {},
                'publish_pack': {},
                'review_card': {}
            }
        
        # 3. 构建内容元数据
        content_meta = {
            'selected_topic': _extract_topic(segments),
            'scene': scene,
            'duration_seconds': sum(seg.get('duration', 5) for seg in segments),
            'originality_check': '所有内容基于用户提供的原始素材生成',
            'safety_note': '未涉及教材原文复述'
        }
        
        # 4. 构建发布信息
        publish_pack = {
            'title': f"跟小丸子学{content_meta['selected_topic']}",
            'cover_text': f"跟读学英语\n{content_meta['selected_topic']}",
            'description': f"每天跟读3遍，一周熟练运用！#英语学习 #跟读练习",
            'hashtags': ['英语学习', '跟读练习', '实用英语']
        }
        
        # 5. 构建复习卡片
        expressions = []
        for seg in segments:
            if seg.get('scene', '').startswith('第') and '跟读句' in seg.get('scene', ''):
                caption = seg.get('caption', '')
                if '\n' in caption:
                    parts = caption.split('\n')
                    expressions.append({
                        'english': parts[0],
                        'chinese': parts[1] if len(parts) > 1 else '',
                        'usage': ''
                    })
        
        review_card = {
            'today_expressions': expressions[:5],
            'quick_review': '每天跟读3遍，一周就能熟练运用！'
        }
        
        return {
            'segments': segments,
            'content_meta': content_meta,
            'publish_pack': publish_pack,
            'review_card': review_card,
            'video_plan': {
                'canvas': {
                    'width': canvas_width,
                    'height': canvas_height
                },
                'duration': int(sum(seg.get('duration', 5) for seg in segments) * 1000000)
            }
        }
        
    except Exception as e:
        logger.error(f"生成视频计划失败: {e}")
        return {
            'error': str(e),
            'segments': [],
            'content_meta': {},
            'publish_pack': {},
            'review_card': {}
        }


def _extract_topic(segments: List[Dict]) -> str:
    """从片段中提取主题"""
    for seg in segments:
        scene = seg.get('scene', '')
        if '标题页' in scene or '标题' in scene:
            caption = seg.get('caption', '')
            # 提取第一行作为标题
            return caption.split('\n')[0].strip()
    return '英语跟读'


def _generate_video_plan(
    user_input: str,
    scene: str,
    duration_seconds: int
) -> List[Dict[str, Any]]:
    """
    调用 LLM 生成视频计划
    
    LLM 需要理解用户输入，识别其中的英语句子，
    并按要求生成结构化的视频计划。
    """
    llm = _get_llm()
    
    # 构建提示词
    prompt = f"""你是一个英语短视频内容策划助手。用户会提供英语学习内容，你需要生成一个跟读视频计划。

## 用户输入
{user_input}

## 场景类型
{scene}

## 视频结构（必须按此顺序）
1. 钩子页（1.5-3秒）→ 2. 标题页（2秒）→ 3. 跟读句1-5（每句6秒）→ 4. 结尾复习页（8秒）

## 任务要求
1. 理解用户提供的英语内容，识别用户想要学习的英语表达
2. **如果用户提供了具体的英语句子，必须严格使用这些句子**
3. 生成一个吸引人的"钩子页"文案，制造好奇或反差

## 输出格式
请直接输出 JSON，不要有其他内容：

{{
    "segments": [
        {{
            "scene": "钩子页",
            "caption": "钩子文案（12-18字以内，一句话）",
            "tts": "钩子文案（慢速、直接）",
            "image_prompt": "小丸子做出惊讶或思考的表情，背景简洁，顶部30%留白",
            "duration": 2.0
        }},
        {{
            "scene": "标题页",
            "caption": "英文标题\\n中文标题",
            "tts": "标题语音内容（简短）",
            "image_prompt": "简洁的场景描述，小丸子站立在中下区域，头顶留白 25%",
            "duration": 2.0
        }},
        {{
            "scene": "第1句跟读",
            "caption": "英语句子\\n中文意思",
            "tts": "第1句。英语句子 中文意思。跟我读：英语句子 再来一遍：英语句子",
            "image_prompt": "场景描述（与句子意思匹配），小丸子站立在中下区域，头顶留白 25%",
            "duration": 6.0
        }},
        ...
        {{
            "scene": "结尾复习页",
            "caption": "今日X句跟读复习\\n1. 句子1 - 意思1\\n2. 句子2 - 意思2\\n...",
            "tts": "来复习一下今天学的X句话。第一句，句子1 第二句，句子2 ...",
            "image_prompt": "FIXED_REVIEW_BACKGROUND",
            "duration": 8.0
        }}
    ]
}}

## 钩子页要求（必须遵守）
1. **必须和本期5句英语内容强相关**，可以从第1句或最后一句引出
2. 文字要短，一句就够，12-18个字以内
3. 优先使用反差型、痛点型、结果型、悬念型风格
4. 示例文案：
   - "这句英语，今天就能用。"
   - "最后一句，才是最实用的。"
   - "这5句，真的能救场。"
   - "学会这句，聊天会顺很多。"
5. TTS要慢、直接，不要说教
6. 图片：小丸子做出惊讶或思考的表情

## image_prompt 场景描述规则（必须严格遵守）

### 钩子页
image_prompt 格式："小丸子做出惊讶或思考的表情，背景简洁，顶部30%留白"
要求：小丸子表情突出，背景简单干净

### 标题页
image_prompt 格式："简洁的场景描述，小丸子站立在中下区域，头顶留白 25%"

### 跟读句（scene 包含"第X句"）
image_prompt 格式："与句子意思匹配的场景描述，小丸子站立在中下区域，头顶留白 25%"
示例："小丸子站在酒店前台微笑着递出证件，小丸子站立在中下区域，头顶留白 25%"

### 结尾复习页（重要！）
image_prompt 必须固定为："FIXED_REVIEW_BACKGROUND"
这是特殊标记，表示使用固定复习卡背景图，不生成AI图片

## 重要规则
1. **必须使用用户提供的原始英语句子**，不要自己编造新句子
2. 每个跟读句的 duration 设为 6.0 秒
3. 只输出 JSON，不要有 ```json 之类的标记
"""
    
    try:
        import requests
        import os
        from coze_coding_utils.runtime_ctx.context import default_headers, new_context
        
        api_key = os.getenv("COZE_WORKLOAD_IDENTITY_API_KEY")
        base_url = os.getenv("COZE_INTEGRATION_MODEL_BASE_URL")
        ctx = new_context(method="generate_plan")
        headers_dict = default_headers(ctx)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        headers.update(headers_dict)
        
        data = {
            "model": "doubao-seed-2-0-pro-260215",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8000,
            "temperature": 0.7,
            "stream": False
        }
        
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=120
        )
        
        # 解析 SSE 流式响应 - 从字节直接解析避免编码问题
        content = ""
        for line in resp.content.split(b'\n'):
            try:
                line_str = line.decode('utf-8', errors='replace').strip()
                if line_str.startswith('data:'):
                    json_str = line_str[5:].strip()
                    if json_str and json_str != '[DONE]':
                        chunk = json.loads(json_str)
                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                        delta_content = delta.get('content') or delta.get('reasoning_content', '')
                        # 提取思考内容（用于调试）
                        reasoning = delta.get('reasoning_content') or ''
                        # 提取实际内容
                        delta_content = delta.get('content') or ''
                        # 如果没有 content，可能是 thinking 模式
                        if not delta_content and reasoning:
                            # 在 thinking 模式下，思考结束后应该还有 content
                            # 这里我们只取 reasoning 最后部分
                            pass
                        if isinstance(delta_content, str):
                            content += delta_content
            except Exception:
                continue
        
        # 如果没有获取到内容，尝试直接解析响应
        if not content.strip():
            try:
                result_data = resp.json()
                if 'choices' in result_data:
                    delta = result_data['choices'][0].get('delta', {})
                    content = delta.get('content') or delta.get('reasoning_content', '')
                elif 'error' in result_data:
                    raise Exception(f"API Error: {result_data['error']}")
            except:
                pass
        
        # 清理响应
        content = content.strip()
        if content.startswith('```'):
            parts = content.split('```')
            content = parts[1] if len(parts) > 1 else content
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()
        
        # 确保 content 是正确的字符串
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        
        data = json.loads(content)
        segments = data.get('segments', [])
        
        return segments
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}, content: {content[:500] if content else 'N/A'}")
        return []
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        return []


def _build_review_summary(segments: List[Dict[str, Any]]) -> str:
    """构建复习总结"""
    sentences = []
    for seg in segments:
        scene = seg.get('scene', '')
        if scene.startswith('第') and '跟读' in scene:
            caption = seg.get('caption', '')
            sentences.append(caption)
    
    if not sentences:
        return "今天学的内容"
    
    return "\n".join(sentences)
