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

from graphs.nodes.topic_memory import get_topic_memory
from graphs.nodes.topic_rescue_node import (
    build_rescue_segments,
    build_scene_collection_segments,
    build_topic_brief,
    detect_scene as detect_topic_scene,
    extract_answer_sentences,
    normalize_dynamic_scene_collection_brief,
    parse_topic_input,
    SCENE_COLLECTION_DURATION_SECONDS,
)

logger = logging.getLogger(__name__)

DEFAULT_SENTENCE_COUNT = 3
MAX_SENTENCE_COUNT = 5
DEFAULT_TARGET_DURATION_SECONDS = 28
MAX_SENTENCE_SEGMENT_SECONDS = 5.0
SUMMARY_SEGMENT_SECONDS = 2.5
PREVIEW_SEGMENT_SECONDS = 2.0

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
    from langchain_openai import ChatOpenAI
    from coze_coding_utils.runtime_ctx.context import default_headers, new_context

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
        raw_topic = state.get('raw_topic', '') or topic or learning_note
        auto_generate_expressions = bool(state.get('auto_generate_expressions'))
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
        
        scene = state.get('scene') or detect_topic_scene(raw_topic)
        duration_seconds = state.get('duration_seconds', DEFAULT_TARGET_DURATION_SECONDS)
        sentence_count = _normalize_sentence_count(state.get('sentence_count', DEFAULT_SENTENCE_COUNT))
        canvas_width = state.get('canvas_width', 1080)
        canvas_height = state.get('canvas_height', 1920)
        
        # 2. 获取或创建专题记忆表
        if not topic_id:
            # 从用户输入生成 topic_id
            topic_id = _generate_topic_id(raw_topic or user_input, scene)
        
        memory = get_topic_memory(topic_id)
        memory_context = memory.get_context_for_plan()
        
        # 3. 调用 LLM 生成视频计划（带记忆上下文）
        topic_brief = {}
        topic_meta = parse_topic_input(raw_topic or user_input)
        if auto_generate_expressions or _should_auto_generate_from_topic(learning_note, topic):
            topic_brief = build_topic_brief(
                raw_topic or user_input,
                memory_context=memory_context,
                content_mode=topic_meta.get("content_mode"),
            )
            scene = topic_brief.get('scene', scene)
            topic_id = topic_brief.get('topic_id') or topic_id
            content_mode = topic_brief.get("content_mode", "painpoint_contrast")
            if content_mode == "scene_collection":
                if duration_seconds == DEFAULT_TARGET_DURATION_SECONDS:
                    duration_seconds = SCENE_COLLECTION_DURATION_SECONDS
                if topic_brief.get("needs_dynamic_generation"):
                    generated_brief = _generate_dynamic_scene_collection_brief(
                        raw_topic=topic_brief.get("raw_topic") or raw_topic or user_input,
                        scene=scene,
                        memory_context=memory_context,
                    )
                    if generated_brief:
                        topic_brief = generated_brief
                        scene = topic_brief.get('scene', scene)
                        topic_id = topic_brief.get('topic_id') or topic_id
                    else:
                        return _build_quality_error(
                            "动态生成场景式内容失败，请换一个更具体的主题再试。",
                            topic_id
                        )
                quality_review = topic_brief.get("quality_review", {})
                if not quality_review.get("is_reasonable", True):
                    return _build_quality_error(
                        "场景式内容质量未通过，已停止生成视频。",
                        topic_id,
                        quality_review
                    )
                segments = build_scene_collection_segments(topic_brief, duration_seconds=duration_seconds)
            else:
                segments = build_rescue_segments(topic_brief, duration_seconds=duration_seconds)
            result = {
                'segments': segments,
                'episode_info': {
                    'season_name': topic_brief.get('topic', raw_topic or user_input),
                    'review': '',
                    'preview': topic_brief.get('next_preview', '')
                }
            }
        else:
            result = _generate_video_plan(
                user_input=user_input,
                scene=scene,
                duration_seconds=duration_seconds,
                sentence_count=sentence_count,
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
        effective_sentence_count = (
            len(extract_answer_sentences(topic_brief))
            if topic_brief else sentence_count
        )
        
        # 4. 更新记忆表
        episode_data = {
            "sentences": extract_answer_sentences(topic_brief) or _extract_sentences(segments),
            "scene": _extract_scene_name(segments),
            "hook": _extract_hook(segments),
            "preview": episode_info.get('preview', ''),
            "pain_point": topic_brief.get("pain_point", ""),
            "wrong_expression": topic_brief.get("wrong_expression", ""),
            "answer_levels": topic_brief.get("answer_levels", []),
            "content_mode": topic_brief.get("content_mode", ""),
            "quality_review": topic_brief.get("quality_review", {}),
        }
        memory.add_episode(episode_data)
        
        # 设置专题名称（如果是第一集）
        if memory.episode_count == 1:
            season_name = _extract_season_name(segments, user_input)
            memory.set_season_name(season_name)
        
        # 5. 构建内容元数据
        content_meta = {
            'selected_topic': _extract_topic(segments, user_input),
            'scene': scene,
            'sub_scene': topic_brief.get('sub_scene') or topic_meta.get('sub_scene'),
            'duration_seconds': sum(seg.get('duration', 5) for seg in segments),
            'target_duration_seconds': duration_seconds,
            'sentence_count': effective_sentence_count,
            'format': _format_for_topic_brief(topic_brief) if topic_brief else 'retention_short',
            'content_mode': topic_brief.get('content_mode') or topic_meta.get('content_mode', 'hybrid'),
            'pain_point': topic_brief.get('pain_point', ''),
            'wrong_expression': topic_brief.get('wrong_expression', ''),
            'quality_review': topic_brief.get('quality_review', {}),
            'voice_profile': topic_brief.get('voice_profile', {}),
            'originality_check': '所有内容基于用户提供的原始素材生成',
            'safety_note': '未涉及教材原文复述',
            'topic_id': topic_id
        }
        
        # 6. 构建发布信息
        publish_pack = _build_publish_pack(content_meta, topic_brief, segments)
        
        # 7. 构建复习卡片
        expressions = []
        for seg in segments:
            if _is_sentence_segment(seg):
                caption = seg.get('caption', '')
                if '\n' in caption:
                    parts = caption.split('\n')
                    expressions.append({
                        'english': parts[0],
                        'chinese': parts[1] if len(parts) > 1 else '',
                        'usage': ''
                    })
        
        review_card = {
            'today_expressions': expressions[:effective_sentence_count],
            'answer_levels': topic_brief.get('answer_levels', []),
            'quick_review': '先收藏，下一集继续同一场景。'
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
        'emergency': ['救场', 'emergency', '听不清', '不会说', '卡壳', '迷路', '丢东西', '付款失败'],
        'restaurant': ['餐厅', 'restaurant', '点餐', '用餐', '吃饭'],
        'airport': ['机场', 'airport', '登机'],
        'shopping': ['购物', 'shopping', '商店', '买'],
        'transport': ['打车', 'taxi', '地铁', '公交', '问路', '导航'],
        'office': ['办公室', 'office', '工作', '会议'],
        'business': ['商务', 'business', '客户', '谈判', '合同', '报价'],
        'parent_child': ['亲子', 'parent', 'child', '孩子', '绘本'],
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


def _should_auto_generate_from_topic(learning_note: str, topic: str) -> bool:
    """Treat a topic-only request as an instruction to generate expressions."""
    if not topic:
        return False
    if not learning_note:
        return True
    # If the user provides English text, keep the legacy sentence-selection path.
    if re.search(r"[A-Za-z]{2,}", learning_note):
        return False
    return len(learning_note.strip()) <= 20


def _build_quality_error(
    message: str,
    topic_id: str = "",
    quality_review: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return {
        'error': message,
        'segments': [],
        'content_meta': {
            'quality_review': quality_review or {},
        },
        'publish_pack': {},
        'review_card': {},
        'episode_info': {},
        'topic_id': topic_id,
    }


def _generate_dynamic_scene_collection_brief(
    raw_topic: str,
    scene: str,
    memory_context: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Use LLM to generate concrete same-scene expressions when no preset matches."""
    learned_sentences = memory_context.get('learned_sentences', []) if memory_context else []
    learned_list = "\n".join(f"- {s}" for s in learned_sentences[-20:]) or "无"
    prompt = f"""你是“小丸子英语”的短视频脚本专家。请根据用户主题动态生成一个【场景式】英语短视频脚本 brief。

## 用户主题
{raw_topic}

## 场景大类
{scene}

## 已学过的句子，禁止重复
{learned_list}

## 目标
生成 5 句同一个具体场景里的真实英语表达，适合 30-45 秒短视频，提升收藏价值。

## 硬性规则
1. 必须正好 5 句 expressions。
2. 5 句必须强相关于用户主题，不能用万能句凑数。
3. 每句都要能在该具体场景直接开口使用。
4. 5 句之间要覆盖不同动作，不能重复表达同一件事。
5. 英文自然、简短、口语化，适合初学者。
6. 禁止使用这些泛句作为主体：
   - Excuse me, could you help me?
   - Could you help me?
   - Could you help me with this?
   - I'd like to ask about this.
   - Could you confirm that for me?
   - Could you say that again?
   - Thanks, that helps a lot.
7. 如果主题是“飞机餐忌口”，应该围绕素食、过敏、不吃某类食物、换餐等具体动作，而不是泛泛求助。

## 输出 JSON，不要 Markdown
{{
  "topic": "短主题名",
  "real_scene": "一句话真实场景",
  "hook": "18字以内强钩子",
  "setup": "一句话说明这5句覆盖什么",
  "expressions": [
    {{
      "label": "动作标签",
      "english": "English sentence",
      "chinese": "中文意思",
      "usage": "这句什么时候用"
    }}
  ],
  "summary_tts": "这5句先收藏...",
  "next_preview": "下集预告",
  "interaction": "评论区互动问题",
  "title": "【主题】吸引眼球标题"
}}
"""
    try:
        import requests
        from coze_coding_utils.runtime_ctx.context import default_headers, new_context

        api_key = os.getenv("COZE_WORKLOAD_IDENTITY_API_KEY")
        base_url = os.getenv("COZE_INTEGRATION_MODEL_BASE_URL")
        if not api_key or not base_url:
            logger.warning("缺少 LLM 环境变量，无法动态生成场景式内容")
            return None

        ctx = new_context(method="dynamic_scene_collection")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        headers.update(default_headers(ctx))
        data = {
            "model": "doubao-seed-2-0-pro-260215",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4000,
            "temperature": 0.45,
            "stream": False,
        }
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=120,
        )
        resp.raise_for_status()
        content = _extract_chat_content(resp).strip()
        if content.startswith('```'):
            parts = content.split('```')
            content = parts[1] if len(parts) > 1 else content
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()
        payload = json.loads(content)
        return normalize_dynamic_scene_collection_brief(raw_topic, scene, payload)
    except Exception as e:
        logger.error(f"动态场景式内容生成失败: {e}")
        return None


def _format_for_topic_brief(topic_brief: Dict[str, Any]) -> str:
    if not topic_brief:
        return 'retention_short'
    if topic_brief.get('content_mode') == 'scene_collection':
        return 'scene_collection'
    return 'topic_rescue_hybrid'


def _build_publish_pack(
    content_meta: Dict[str, Any],
    topic_brief: Dict[str, Any],
    segments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    topic = topic_brief.get('topic') or content_meta.get('selected_topic') or '真实场景英语'
    mode = topic_brief.get('content_mode') or content_meta.get('content_mode')

    if mode == 'scene_collection':
        title = topic_brief.get('title') or f"【{topic}】这5句英语真的能救场"
        description = (
            f"每天进步一点点。{topic}真实场景 5 句英语，先收藏，"
            "关键时候能直接用。#英语学习 #实用英语 #旅游英语"
        )
        hashtags = ['英语学习', '实用英语', '旅游英语']
    else:
        pain_point = topic_brief.get('pain_point') or content_meta.get('selected_topic') or topic
        title = _build_painpoint_title(topic, pain_point)
        description = (
            f"每天进步一点点。别再硬翻译，{topic}这句先学会。"
            "#英语学习 #实用英语 #救场英语"
        )
        hashtags = ['英语学习', '实用英语', '救场英语']

    return {
        'title': title[:30],
        'cover_text': topic[:12],
        'description': description,
        'hashtags': hashtags,
    }


def _build_painpoint_title(topic: str, pain_point: str) -> str:
    if "空乘" in pain_point or "空姐" in pain_point:
        return f"【{topic}】别只会yes，这句才有用"
    if "托运" in pain_point or "行李" in pain_point:
        return f"【{topic}】不会说托运行李？这句能救场"
    if "账单" in pain_point:
        return f"【{topic}】账单多收费？这句一定要会"
    if "太吵" in pain_point or "换房" in pain_point:
        return f"【{topic}】房间太吵？这句帮你换房"
    if "入境" in pain_point:
        return f"【{topic}】被问来干嘛？别只会travel"
    return f"【{topic}】不会开口？这句能救场"


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
    hook = _extract_hook(segments)
    if hook:
        return hook
    for seg in segments:
        if '标题' in seg.get('scene', ''):
            caption = seg.get('caption', '')
            if '\n' in caption:
                return caption.split('\n')[-1].strip()
            return caption.strip()
    return ''


def _extract_hook(segments: List[Dict]) -> str:
    """Extract the current episode hook for topic memory."""
    for seg in segments:
        if '钩子' in seg.get('scene', ''):
            return seg.get('caption', '').replace('\n', ' ').strip()
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


def _extract_topic(segments: List[Dict], user_input: str = '') -> str:
    """从片段中提取主题"""
    for seg in segments:
        scene = seg.get('scene', '')
        if '标题页' in scene or '标题' in scene:
            caption = seg.get('caption', '')
            # 提取第一行作为标题
            return caption.split('\n')[0].strip()
    hook = _extract_hook(segments)
    if hook:
        return hook[:18]
    return user_input[:18] if user_input else '真实场景英语'


def _normalize_sentence_count(value: Any) -> int:
    """Normalize requested sentence count for short-video retention testing."""
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = DEFAULT_SENTENCE_COUNT
    return max(1, min(count, MAX_SENTENCE_COUNT))


def _is_sentence_segment(segment: Dict[str, Any]) -> bool:
    scene = segment.get('scene', '')
    return scene.startswith('第') and ('句' in scene or '跟读' in scene)


def _sanitize_tts_text(text: str) -> str:
    """Remove legacy repeated read-aloud wording that stretches retention videos."""
    text = (text or '').strip()
    text = re.sub(r'再来一遍[:：]?.*$', '', text).strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def _compact_caption(caption: str, max_lines: int = 2) -> str:
    lines = [line.strip() for line in (caption or '').splitlines() if line.strip()]
    return "\n".join(lines[:max_lines])


def _normalize_segments_for_retention(
    segments: List[Dict[str, Any]],
    sentence_count: int
) -> List[Dict[str, Any]]:
    """Keep the generated plan in the fast short-video shape."""
    normalized: List[Dict[str, Any]] = []
    sentence_seen = 0

    for segment in segments:
        if not isinstance(segment, dict):
            continue
        scene = segment.get('scene', '')

        if '回顾' in scene or '标题' in scene:
            continue

        if _is_sentence_segment(segment):
            sentence_seen += 1
            if sentence_seen > sentence_count:
                continue

            updated = dict(segment)
            updated['scene'] = f"第{sentence_seen}句跟读"
            updated['caption'] = _compact_caption(updated.get('caption', ''), max_lines=2)
            updated['tts'] = _sanitize_tts_text(updated.get('tts', ''))
            updated['duration'] = min(float(updated.get('duration', MAX_SENTENCE_SEGMENT_SECONDS)), MAX_SENTENCE_SEGMENT_SECONDS)
            normalized.append(updated)
            continue

        updated = dict(segment)
        updated['tts'] = _sanitize_tts_text(updated.get('tts', ''))

        if '复习' in scene or '汇总' in scene or '总结' in scene:
            updated['scene'] = '快速汇总页'
            updated['tts'] = '这几句先收藏，下一集继续学同一场景。'
            updated['duration'] = SUMMARY_SEGMENT_SECONDS
            updated['image_prompt'] = 'FIXED_REVIEW_WITH_CHAR'
            # 复习页面不限制行数，显示所有句子
            updated['caption'] = updated.get('caption', '')
        elif '预告' in scene:
            updated['duration'] = PREVIEW_SEGMENT_SECONDS
            updated['image_prompt'] = 'FIXED_HOOK_IMAGE'
            updated['caption'] = _compact_caption(updated.get('caption', ''), max_lines=2)
        elif '钩子' in scene:
            updated['duration'] = min(float(updated.get('duration', 2.0)), 2.0)
            updated['image_prompt'] = 'FIXED_HOOK_IMAGE'
            updated['caption'] = _compact_caption(updated.get('caption', ''), max_lines=2)
        else:
            updated['caption'] = _compact_caption(updated.get('caption', ''), max_lines=2)

        normalized.append(updated)

    if not any('预告' in seg.get('scene', '') for seg in normalized):
        normalized.append({
            'scene': '预告页',
            'caption': '下一集继续救场',
            'tts': '下一集继续学同一场景。',
            'image_prompt': 'FIXED_HOOK_IMAGE',
            'duration': PREVIEW_SEGMENT_SECONDS
        })

    return normalized


def _extract_chat_content(resp: Any) -> str:
    """Extract assistant content from both standard JSON and SSE-like responses."""
    content = ""

    try:
        payload = resp.json()
        choices = payload.get('choices') or []
        if choices:
            message = choices[0].get('message') or {}
            content = message.get('content') or ''
            if content:
                return content
            delta = choices[0].get('delta') or {}
            content = delta.get('content') or ''
            if content:
                return content
    except Exception:
        pass

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

    return content


def _generate_video_plan(
    user_input: str,
    scene: str,
    duration_seconds: int,
    sentence_count: int = DEFAULT_SENTENCE_COUNT,
    memory_context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    调用 LLM 生成视频计划（专题追剧式连续内容）
    
    支持：
    - 上集回顾
    - 本集新内容
    - 下集预告
    """
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
    prompt = f"""你是“小丸子英语”短视频策划助手。你的目标不是做完整课程，而是做高完播率的真实场景救场英语短视频。

## 账号定位
- 主角：小丸子，年轻女性打工人英语学习搭子
- 气质：亲切、元气、有陪伴感，不说教，不过度搞笑
- 内容方向：碎片时间学真实场景英语
- 当前优化目标：提高完播率，视频必须短、快、真实、有下一集连续感

## 用户输入
{user_input}

## 场景类型
{scene}

## 专题信息
- 专题名称：{season_name or '新专题'}
- {review_hint}

## 已学过的句子（不要重复！）
{learned_list}

## 视频结构（必须按此顺序）
1. 钩子页（1.5-2秒）→ 2. 跟读句1-{sentence_count}（每句4-5秒）→ 3. 快速汇总页（2-3秒）→ 4. 预告/互动页（2秒）

## 时长目标
- 目标总时长：{duration_seconds}秒以内
- 每张图不要超过5秒
- 禁止为了凑时长拉长图片或重复朗读
- 不要生成回顾页和标题页，开头直接进入强场景钩子

## 任务要求
1. 理解用户提供的英语内容，识别用户想要学习的英语表达
2. **跟读句必须正好{sentence_count}个**：
   - 如果用户提供了{sentence_count}个或以上句子，从中选择最能救场、最真实的{sentence_count}个
   - 如果用户提供的句子不足{sentence_count}个，根据同一主题自动补充到{sentence_count}个
   - 补充的句子必须与用户提供的句子属于同一场景、难度相当
3. 生成一个真实尴尬场景钩子，不要普通标题式开头
4. 每句 TTS 固定格式：第N句。英文句子。中文意思。跟我读：英文句子。
5. 禁止出现“再来一遍”
6. 汇总页只展示本集句子，TTS 只说一句：这几句先收藏，下一集继续学同一场景。
7. 预告页要承接同一场景，带轻互动，不要只说关注

## 输出格式
请直接输出 JSON，不要有其他内容：

{{
    "episode_info": {{
        "season_name": "{season_name or '新专题'}",
        "review": "上集回顾文案（首次为空字符串）",
        "preview": "预告文案（留悬念）"
    }},
    "segments": [
        {{
            "scene": "钩子页",
            "caption": "真实尴尬场景钩子（18字以内）",
            "tts": "真实尴尬场景钩子，短促直接",
            "image_prompt": "FIXED_HOOK_IMAGE",
            "duration": 2.0
        }},
        {{
            "scene": "第1句跟读",
            "caption": "英语句子\\n中文意思",
            "tts": "第1句。英语句子。中文意思。跟我读：英语句子。",
            "image_prompt": "场景描述，小丸子站立在中下区域，头顶留白 25%",
            "duration": 4.5
        }},
        ...
        {{
            "scene": "快速汇总页",
            "caption": "1. 句子1\\n2. 句子2\\n3. 句子3",
            "tts": "这几句先收藏，下一集继续学同一场景。",
            "image_prompt": "FIXED_REVIEW_WITH_CHAR",
            "duration": 2.5
        }},
        {{
            "scene": "预告页",
            "caption": "下集预告\\n轻互动文案",
            "tts": "轻互动预告，比如：评论区打酒店，我继续更下一集。",
            "image_prompt": "FIXED_HOOK_IMAGE",
            "duration": 2.0
        }}
    ]
}}

## 钩子页规则
1. **必须和本期{sentence_count}句英语内容强相关**
2. 文字要短，18字以内
3. 必须指向真实尴尬场景，优先使用反差型、痛点型、悬念型风格
4. 示例：
   - "酒店问押金，别只会yes"
   - "机场问行李，这句能救场"
   - "入境官追问，先背这几句"

## 预告页规则（必须留悬念！）
1. 预告接下来要学的同一场景内容
2. 制造期待感，并带轻互动
3. 示例：
   - "下集学房间投诉，评论区打酒店"
   - "下一集学账单多收费怎么说"
   - "这句你敢不敢跟读一遍？"

## image_prompt 规则
- 钩子页、预告页：固定为 "FIXED_HOOK_IMAGE"
- 标题页、跟读句：描述场景，小丸子在中下区域
- 快速汇总页：固定为 "FIXED_REVIEW_WITH_CHAR"

## 重要规则
1. 优先使用用户提供的原始英语句子；不足时才补充
2. **不要重复已学过的句子**
3. 每个跟读句的 duration 设为 4.0-5.0 秒
4. 只输出 JSON，不要有 ```json 之类的标记
5. 字幕每屏最多两行，英文在上，中文在下
6. 不要生成“每天跟读3遍”“一周熟练运用”等慢课式文案
7. 不要出现"第X集"概念，用户会手动添加合集
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
        resp.raise_for_status()
        
        # 清理响应
        content = _extract_chat_content(resp).strip()
        if content.startswith('```'):
            parts = content.split('```')
            content = parts[1] if len(parts) > 1 else content
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()
        
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        
        data = json.loads(content)
        segments = _normalize_segments_for_retention(
            data.get('segments', []),
            sentence_count=sentence_count
        )
        return {
            'segments': segments,
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
