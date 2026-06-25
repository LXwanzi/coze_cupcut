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
from graphs.nodes.topic_memory import get_topic_memory

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
    生成视频计划（专题追剧式连续内容）
    
    支持的输入格式：
    - learning_note: 字符串，用户的学习笔记或英语句子
    - topic: 字符串，简单的主题描述
    - topic_id: 字符串（可选），专题ID，用于关联记忆表
    - image_url: 字符串（可选），用户提供参考图片
    - scene: 字符串（可选），场景类型
    
    输出：
    - segments: 视频片段列表
    - content_meta: 内容元数据
    - publish_pack: 发布信息
    - review_card: 复习卡片
    - episode_info: 集数信息（回顾、预告等）
    """
    try:
        # 1. 提取用户输入
        learning_note = state.get('learning_note', '')
        topic = state.get('topic', '')
        topic_id = state.get('topic_id', '')
        user_input = learning_note or topic
        
        if not user_input:
            return {
                'error': '请提供学习内容或主题',
                'segments': [],
                'content_meta': {},
                'publish_pack': {},
                'review_card': {},
                'episode_info': {}
            }
        
        scene = state.get('scene', 'travel')
        duration_seconds = state.get('duration_seconds', 60)
        canvas_width = state.get('canvas_width', 1080)
        canvas_height = state.get('canvas_height', 1920)
        
        # 2. 获取或创建专题记忆表
        if not topic_id:
            # 从用户输入生成 topic_id
            topic_id = _generate_topic_id(user_input, scene)
        
        memory = get_topic_memory(topic_id)
        memory_context = memory.get_context_for_plan()
        
        # 3. 调用 LLM 生成视频计划（带记忆上下文）
        result = _generate_video_plan(
            user_input=user_input,
            scene=scene,
            duration_seconds=duration_seconds,
            memory_context=memory_context
        )
        
        if not result or not result.get('segments'):
            return {
                'error': '未能生成视频计划',
                'segments': [],
                'content_meta': {},
                'publish_pack': {},
                'review_card': {},
                'episode_info': {},
                'topic_id': topic_id
            }
        
        segments = result['segments']
        episode_info = result.get('episode_info', {})
        
        # 4. 更新记忆表
        episode_data = {
            "sentences": _extract_sentences(segments),
            "scene": _extract_scene_name(segments),
            "hook": episode_info.get('review', ''),
            "preview": episode_info.get('preview', '')
        }
        memory.add_episode(episode_data)
        
        # 设置专题名称（如果是第一集）
        if memory.episode_count == 1:
            season_name = _extract_season_name(segments, user_input)
            memory.set_season_name(season_name)
        
        # 5. 构建内容元数据
        content_meta = {
            'selected_topic': _extract_topic(segments),
            'scene': scene,
            'duration_seconds': sum(seg.get('duration', 5) for seg in segments),
            'originality_check': '所有内容基于用户提供的原始素材生成',
            'safety_note': '未涉及教材原文复述',
            'topic_id': topic_id,
            'episode_num': memory.episode_count
        }
        
        # 6. 构建发布信息
        publish_pack = {
            'title': f"第{memory.episode_count}集 | 跟小丸子学{content_meta['selected_topic']}",
            'cover_text': f"第{memory.episode_count}集\n{content_meta['selected_topic']}",
            'description': f"每天跟读3遍，一周熟练运用！#英语学习 #跟读练习",
            'hashtags': ['英语学习', '跟读练习', '实用英语']
        }
        
        # 7. 构建复习卡片
        expressions = []
        for seg in segments:
            if seg.get('scene', '').startswith('第') and '跟读' in seg.get('scene', ''):
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
            'episode_info': episode_info,
            'topic_id': topic_id,
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
            'review_card': {},
            'episode_info': {},
            'topic_id': topic_id if 'topic_id' in locals() else ''
        }


def _generate_topic_id(user_input: str, scene: str) -> str:
    """从用户输入生成 topic_id，基于大类主题而非具体场景"""
    import hashlib
    import re
    
    # 定义大类主题映射（同一大类的所有场景共享同一个 topic_id）
    topic_categories = {
        'hotel': ['酒店', 'hotel', 'check in', 'check out', 'check-in', 'check-out', '退房', '入住', '换房', '房间'],
        'travel': ['旅行', 'travel', '旅游', '出行', '行程', 'itinerary', '护照', 'passport', '航班', 'flight'],
        'restaurant': ['餐厅', 'restaurant', '点餐', '用餐', '吃饭'],
        'airport': ['机场', 'airport', '登机'],
        'shopping': ['购物', 'shopping', '商店', '买'],
        'transport': ['打车', 'taxi', '地铁', '公交', '问路', '导航'],
        'office': ['办公室', 'office', '工作', '会议'],
        'daily': ['日常', 'daily', '生活'],
    }
    
    # 查找匹配的大类主题
    topic_category = scene  # 默认使用 scene
    user_input_lower = user_input.lower()
    
    for category, keywords in topic_categories.items():
        for keyword in keywords:
            if keyword.lower() in user_input_lower:
                topic_category = category
                break
        if topic_category != scene:
            break
    
    key = f"{scene}_{topic_category}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _extract_sentences(segments: List[Dict]) -> List[str]:
    """从片段中提取英语句子"""
    sentences = []
    for seg in segments:
        if seg.get('scene', '').startswith('第') and '跟读' in seg.get('scene', ''):
            caption = seg.get('caption', '')
            if '\n' in caption:
                sentences.append(caption.split('\n')[0].strip())
            else:
                sentences.append(caption.strip())
    return sentences


def _extract_scene_name(segments: List[Dict]) -> str:
    """从片段中提取场景名称"""
    for seg in segments:
        if '标题' in seg.get('scene', ''):
            caption = seg.get('caption', '')
            if '\n' in caption:
                return caption.split('\n')[-1].strip()
            return caption.strip()
    return ''


def _extract_season_name(segments: List[Dict], user_input: str) -> str:
    """提取专题名称"""
    for seg in segments:
        if '标题' in seg.get('scene', ''):
            caption = seg.get('caption', '')
            if '\n' in caption:
                parts = caption.split('\n')
                for p in parts:
                    if any('\u4e00' <= c <= '\u9fff' for c in p):
                        return p.strip()
    return user_input[:20] if len(user_input) > 20 else user_input


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
    duration_seconds: int,
    memory_context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    调用 LLM 生成视频计划（专题追剧式连续内容）
    
    支持：
    - 上集回顾
    - 本集新内容
    - 下集预告
    """
    llm = _get_llm()
    
    # 构建记忆上下文
    if memory_context is None:
        memory_context = {}
    
    episode_num = memory_context.get('episode_num', 1)
    season_name = memory_context.get('season_name', '')
    previous_review = memory_context.get('previous_review', '')
    previous_preview = memory_context.get('previous_preview', '')
    learned_sentences = memory_context.get('learned_sentences', [])
    used_scenes = memory_context.get('used_scenes', [])
    
    # 构建回顾文案
    if episode_num > 1 and previous_review:
        review_hint = f"上集回顾：{previous_review}"
    else:
        review_hint = "这是第一集，不需要回顾"
    
    # 构建已学句子列表
    learned_list = "\n".join([f"- {s}" for s in learned_sentences[-10:]]) if learned_sentences else "无"
    
    # 构建提示词
    prompt = f"""你是一个英语短视频内容策划助手。用户会提供英语学习内容，你需要生成一个**专题追剧式**的跟读视频计划。

## 用户输入
{user_input}

## 场景类型
{scene}

## 专题信息
- 专题名称：{season_name or '新专题'}
- 当前集数：第{episode_num}集
- {review_hint}

## 已学过的句子（不要重复！）
{learned_list}

## 视频结构（必须按此顺序）
1. 回顾页（2秒）→ 2. 钩子页（2.5秒）→ 3. 标题页（3秒）→ 4. 跟读句1-5（每句6秒）→ 5. 预告页（3秒）→ 6. 结尾复习页（8秒）

## 任务要求
1. 理解用户提供的英语内容，识别用户想要学习的英语表达
2. **跟读句必须正好5个**：
   - 如果用户提供了5个或以上句子，从中选择5个最合适的
   - 如果用户提供的句子不足5个，根据同一主题自动补充相关句子到5个
   - 补充的句子必须与用户提供的句子属于同一场景、难度相当
3. 生成回顾文案（如果是第2集以上）
4. 生成一个吸引人的"钩子页"文案
5. 生成下集预告文案（留悬念）

## 输出格式
请直接输出 JSON，不要有其他内容：

{{
    "episode_info": {{
        "episode_num": {episode_num},
        "season_name": "{season_name or '新专题'}",
        "review": "上集回顾文案（第1集为空字符串）",
        "preview": "下集预告文案（留悬念）"
    }},
    "segments": [
        {{
            "scene": "回顾页",
            "caption": "上集回顾\\n简短回顾文案",
            "tts": "上集我们学了...这集继续...",
            "image_prompt": "FIXED_HOOK_IMAGE",
            "duration": 2.0
        }},
        {{
            "scene": "钩子页",
            "caption": "钩子文案（12-18字以内）",
            "tts": "钩子文案（慢速、直接）",
            "image_prompt": "FIXED_HOOK_IMAGE",
            "duration": 2.5
        }},
        {{
            "scene": "标题页",
            "caption": "第X集\\n英文标题\\n中文标题",
            "tts": "第X集，标题语音内容",
            "image_prompt": "简洁的场景描述，小丸子站立在中下区域，头顶留白 25%",
            "duration": 3.0
        }},
        {{
            "scene": "第1句跟读",
            "caption": "英语句子\\n中文意思",
            "tts": "第1句。英语句子 中文意思。跟我读：英语句子 再来一遍：英语句子",
            "image_prompt": "场景描述，小丸子站立在中下区域，头顶留白 25%",
            "duration": 6.0
        }},
        ...
        {{
            "scene": "预告页",
            "caption": "下集预告\\n悬念文案",
            "tts": "下一集，我们学更实用的说法...",
            "image_prompt": "FIXED_HOOK_IMAGE",
            "duration": 3.0
        }},
        {{
            "scene": "结尾复习页",
            "caption": "本集X句跟读复习\\n1. 句子1 - 意思1\\n2. 句子2 - 意思2\\n...",
            "tts": "来复习一下本集学的X句话...",
            "image_prompt": "FIXED_REVIEW_WITH_CHAR",
            "duration": 8.0
        }}
    ]
}}

## 回顾页规则（第1集跳过）
- 如果是第1集，回顾页文案为空，duration设为0
- 如果是第2集以上，用一句话回顾上集内容
- 示例："上集我们学了check in，这集继续学..."

## 钩子页规则
1. **必须和本期5句英语内容强相关**
2. 文字要短，12-18个字以内
3. 优先使用反差型、痛点型、悬念型风格
4. 示例：
   - "这句英语，今天就能用。"
   - "最后一句，才是最实用的。"
   - "这5句，真的能救场。"

## 预告页规则（必须留悬念！）
1. 预告下一集的内容
2. 制造期待感，让人想看下一集
3. 示例：
   - "下一集，我们学更自然的说法"
   - "还有一句更像老外会说的"
   - "下集我给你看最实用的版本"

## image_prompt 规则
- 钩子页、回顾页、预告页：固定为 "FIXED_HOOK_IMAGE"
- 标题页、跟读句：描述场景，小丸子在中下区域
- 结尾复习页：固定为 "FIXED_REVIEW_WITH_CHAR"

## 重要规则
1. **必须使用用户提供的原始英语句子**，不要自己编造
2. **不要重复已学过的句子**
3. 每个跟读句的 duration 设为 6.0 秒
4. 只输出 JSON，不要有 ```json 之类的标记
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
        
        # 解析 SSE 流式响应
        content = ""
        for line in resp.content.split(b'\n'):
            try:
                line_str = line.decode('utf-8', errors='replace').strip()
                if line_str.startswith('data:'):
                    json_str = line_str[5:].strip()
                    if json_str and json_str != '[DONE]':
                        chunk = json.loads(json_str)
                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                        delta_content = delta.get('content') or ''
                        if isinstance(delta_content, str):
                            content += delta_content
            except Exception:
                continue
        
        # 清理响应
        content = content.strip()
        if content.startswith('```'):
            parts = content.split('```')
            content = parts[1] if len(parts) > 1 else content
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()
        
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        
        data = json.loads(content)
        return {
            'segments': data.get('segments', []),
            'episode_info': data.get('episode_info', {})
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}, content: {content[:500] if content else 'N/A'}")
        return {'segments': [], 'episode_info': {}}
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        return {'segments': [], 'episode_info': {}}


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
