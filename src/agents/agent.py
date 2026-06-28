"""Multi-account short-video generation Agent."""
import os
import json
import logging
import re
from typing import Dict, Any, List

from content.account_loader import get_account_pack

logger = logging.getLogger(__name__)
DEFAULT_SHORT_DURATION_SECONDS = 28
DEFAULT_SHORT_SENTENCE_COUNT = 3
ACCOUNT_PACK = get_account_pack()
VOICE_CONFIG = ACCOUNT_PACK.get("voices", {})
CONTENT_MODE_PREFIXES = list(
    (ACCOUNT_PACK.get("modes", {}).get("mode_aliases") or {
        '场景式': 'scene_collection',
        '场景': 'scene_collection',
        '合集': 'scene_collection',
        '痛点式': 'painpoint_contrast',
        '痛点': 'painpoint_contrast',
        '反差': 'painpoint_contrast',
        '纠错': 'painpoint_contrast',
    }).keys()
)
VOICE_CONTROL_KEYS = {"音色", "voice", "语速", "speed"}

# LLM 配置
LLM_CONFIG_PATH = os.path.join(
    os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects"),
    "config", "agent_llm_config.json"
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
        default_headers=default_headers(new_context(method="agent"))
    )


def _parse_user_input(message: str) -> Dict[str, Any]:
    """
    解析用户输入，提取学习内容
    
    支持的输入格式：
    1. 纯文本：英语句子或学习笔记
    2. 带主题的文本：如"酒店退房：I'd like to check out, please."
    3. 带场景的文本：如"旅行英语：机场值机"
    """
    result = {
        'raw_topic': '',
        'learning_note': '',
        'topic': '',
        'scene': 'travel',
        'auto_generate_expressions': True,
        'voice_profile_override': {},
    }
    
    if not message or not message.strip():
        return result
    
    message = message.strip()
    message, voice_profile_override = _extract_voice_profile_override(message)
    result['voice_profile_override'] = voice_profile_override
    if not message:
        return result
    
    # 尝试提取主题/场景
    if '：' in message or ':' in message:
        parts = message.split('：' if '：' in message else ':', 1)
        if len(parts) == 2:
            topic_part = parts[0].strip()
            content_part = parts[1].strip()

            if topic_part in CONTENT_MODE_PREFIXES:
                result['raw_topic'] = f"{topic_part}：{content_part}"
                result['topic'] = f"{topic_part}：{content_part}"
                result['learning_note'] = ''
                result['scene'] = _detect_scene(content_part)
                result['auto_generate_expressions'] = True
                return result
            
            # 判断是否是场景描述
            scene_keywords = ['酒店', '旅行', '机场', '餐厅', '购物', '医院', '银行', '办公室', '商务', '亲子', '救场', '生活']
            if any(kw in topic_part for kw in scene_keywords):
                result['topic'] = topic_part
                result['learning_note'] = content_part
                result['scene'] = _detect_scene(topic_part)
                result['raw_topic'] = topic_part
                result['auto_generate_expressions'] = not _contains_english(content_part)
            else:
                result['learning_note'] = message
                result['auto_generate_expressions'] = False
        else:
            result['learning_note'] = message
            result['auto_generate_expressions'] = False
    else:
        result['raw_topic'] = message
        result['topic'] = message
        result['learning_note'] = ''
        result['scene'] = _detect_scene(message)
        result['auto_generate_expressions'] = True
    
    return result


def _contains_english(text: str) -> bool:
    return bool(text and any(("A" <= ch <= "Z") or ("a" <= ch <= "z") for ch in text))


def _extract_voice_profile_override(message: str) -> tuple[str, Dict[str, Any]]:
    """Extract optional voice controls without passing them to topic generation."""
    override: Dict[str, Any] = {}
    kept_lines: List[str] = []

    for line in (message or "").splitlines():
        clean_line = line.strip()
        if not clean_line:
            continue

        matched = False
        for separator in ("：", ":"):
            if separator not in clean_line:
                continue
            key, value = clean_line.split(separator, 1)
            key = key.strip().lower()
            value = value.strip()
            if key not in VOICE_CONTROL_KEYS:
                continue
            matched = True
            if key in {"音色", "voice"} and value:
                voice = _normalize_voice_value(value)
                if voice:
                    override["voice"] = voice
            elif key in {"语速", "speed"} and value:
                speed = _normalize_speed_value(value)
                if speed is not None:
                    override["speed"] = speed
            break

        if not matched:
            kept_lines.append(clean_line)

    return "\n".join(kept_lines).strip(), override


def _normalize_voice_value(value: str) -> str:
    voice = (value or "").strip()
    if not voice:
        return ""

    aliases = VOICE_CONFIG.get("aliases", {})
    speaker_map = VOICE_CONFIG.get("speaker_map", {})
    allowed = set(VOICE_CONFIG.get("allowed_voice_keys", []))
    normalized = aliases.get(voice, voice)
    if normalized in allowed or normalized in speaker_map or _looks_like_tts_voice_code(normalized):
        return normalized
    return ""


def _looks_like_tts_voice_code(value: str) -> bool:
    return bool(re.match(r"^(zh|saturn|multi|en)_[-_a-zA-Z0-9]+$", value or ""))


def _normalize_speed_value(value: str) -> float | None:
    try:
        speed = float(value)
    except (TypeError, ValueError):
        return None
    speed_range = VOICE_CONFIG.get("speed_range") or [0.8, 1.3]
    try:
        min_speed, max_speed = float(speed_range[0]), float(speed_range[1])
    except (TypeError, ValueError, IndexError):
        min_speed, max_speed = 0.8, 1.3
    return max(min_speed, min(speed, max_speed))


def _detect_scene(text: str) -> str:
    """Map Chinese topic hints to the coarse scene used by the workflow memory."""
    text = text or ''
    scene_map = [
        ('emergency', ['救场', '卡壳', '听不清', '不会说', '付款失败', '迷路', '丢东西']),
        ('hotel', ['酒店', '入住', '退房', '房间', '前台', '押金', '早餐']),
        ('office', ['办公室', '开会', '请假', '催进度', '汇报', '同事']),
        ('business', ['商务', '客户', '合同', '谈判', '报价', '提案']),
        ('parent_child', ['亲子', '孩子', '绘本', '睡前']),
        ('daily', ['日常', '生活', '咖啡', '外卖', '超市', '理发']),
        ('travel', ['旅行', '机场', '入境', '航班', '行李', '登机', '护照']),
    ]
    for scene, keywords in scene_map:
        if any(keyword in text for keyword in keywords):
            return scene
    return 'travel'


async def _run_workflow(user_input: Dict[str, Any]) -> Dict[str, Any]:
    """运行视频生成工作流"""
    try:
        from graphs.graph import create_workflow

        workflow = create_workflow()
        
        # 构建工作流输入
        workflow_input = {
            'raw_topic': user_input.get('raw_topic', ''),
            'learning_note': user_input.get('learning_note', ''),
            'topic': user_input.get('topic', ''),
            'scene': user_input.get('scene', 'travel'),
            'auto_generate_expressions': user_input.get('auto_generate_expressions', True),
            'duration_seconds': DEFAULT_SHORT_DURATION_SECONDS,
            'sentence_count': DEFAULT_SHORT_SENTENCE_COUNT,
            'voice_profile_override': user_input.get('voice_profile_override', {}),
            'canvas_width': 1080,
            'canvas_height': 1920
        }
        
        # 运行工作流
        result = await workflow.ainvoke(workflow_input)
        
        return result
    except Exception as e:
        logger.error(f"工作流执行失败: {e}", exc_info=True)
        return {
            'error': str(e),
            'success': False
        }


def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Agent 节点：处理用户消息并生成视频
    
    流程：
    1. 接收用户的聊天消息
    2. 解析用户输入，提取学习内容
    3. 调用工作流图生成视频
    4. 返回视频生成结果
    """
    import asyncio
    from langchain_core.messages import AIMessage, HumanMessage
    
    messages = state.get('messages', [])
    
    # 获取最后一条用户消息
    user_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) or getattr(msg, "type", "") == "human":
            # content 可能是字符串或列表
            content = msg.content
            if isinstance(content, list):
                # 提取文本内容
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get('type') == 'text':
                        text_parts.append(part.get('text', ''))
                    elif isinstance(part, str):
                        text_parts.append(part)
                user_message = ' '.join(text_parts)
            elif isinstance(content, str):
                user_message = content
            break
    
    if not user_message:
        return {
            'messages': [AIMessage(content="请提供您想学习的英语内容或主题。")]
        }
    
    # 解析用户输入
    user_input = _parse_user_input(user_message)
    
    if not user_input.get('learning_note') and not user_input.get('topic'):
        return {
            'messages': [AIMessage(content="请提供您想学习的英语内容，例如：\n- 酒店退房：I'd like to check out, please.\n- 旅行英语：机场值机")]
        }
    
    # 运行工作流（同步方式）
    try:
        from graphs.graph import create_workflow

        workflow = create_workflow()
        
        # 构建工作流输入
        workflow_input = {
            'raw_topic': user_input.get('raw_topic', ''),
            'learning_note': user_input.get('learning_note', ''),
            'topic': user_input.get('topic', ''),
            'scene': user_input.get('scene', 'travel'),
            'auto_generate_expressions': user_input.get('auto_generate_expressions', True),
            'duration_seconds': DEFAULT_SHORT_DURATION_SECONDS,
            'sentence_count': DEFAULT_SHORT_SENTENCE_COUNT,
            'voice_profile_override': user_input.get('voice_profile_override', {}),
            'canvas_width': 1080,
            'canvas_height': 1920
        }
        
        # 运行工作流（同步）
        result = workflow.invoke(workflow_input)
        
    except Exception as e:
        logger.error(f"工作流执行失败: {e}", exc_info=True)
        return {
            'messages': [AIMessage(content=f"视频生成失败：{str(e)}")]
        }
    
    if result.get('error'):
        return {
            'messages': [AIMessage(content=f"视频生成失败：{result.get('error')}")]
        }
    
    # 构建成功响应
    draft_url = result.get('draft_url', '')
    topic = user_input.get('topic', '英语学习')
    
    response = f"✅ 视频生成成功！\n\n"
    response += f"主题：{topic}\n"
    content_meta = result.get('content_meta', {}) or {}
    if content_meta.get('pain_point'):
        response += f"本集痛点：{content_meta.get('pain_point')}\n"
    if content_meta.get('content_mode'):
        response += f"内容模式：{content_meta.get('content_mode')}\n"
    
    if draft_url:
        response += f"剪映草稿链接：{draft_url}\n"
    if result.get('output_dir'):
        response += f"输出目录：{result.get('output_dir')}\n"
    
    # 添加视频内容摘要
    segments = result.get('segments', [])
    if segments:
        response += f"\n视频包含 {len(segments)} 个片段：\n"
        for i, seg in enumerate(segments[:3], 1):
            summary = seg.get('caption') or seg.get('scene', '')
            if summary:
                summary = summary.replace('\n', ' / ')
                response += f"{i}. {summary[:50]}...\n" if len(summary) > 50 else f"{i}. {summary}\n"
    
    response += "\n请在剪映中打开草稿链接进行编辑和导出。"
    
    return {
        'messages': [AIMessage(content=response)]
    }


def build_agent(ctx=None):
    """
    构建聊天 Agent
    
    这个 Agent 能够：
    1. 接收用户的聊天消息
    2. 解析用户输入，提取学习内容
    3. 调用视频生成工作流
    4. 返回视频生成结果
    """
    from langgraph.graph import StateGraph, MessagesState, END
    from langgraph.checkpoint.memory import MemorySaver

    # 创建 Agent 图
    workflow = StateGraph(MessagesState)
    
    # 添加 Agent 节点
    workflow.add_node("agent", agent_node)
    
    # 设置入口点
    workflow.set_entry_point("agent")
    
    # 添加边
    workflow.add_edge("agent", END)
    
    # 编译图（带记忆）
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
