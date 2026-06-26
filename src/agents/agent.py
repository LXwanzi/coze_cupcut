"""
小丸子英语短视频生成助手 Agent
把每日英语学习笔记转化为原创短视频内容
"""
import os
import json
import logging
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver

from coze_coding_utils.runtime_ctx.context import default_headers, new_context
from graphs.graph import create_workflow

logger = logging.getLogger(__name__)
DEFAULT_SHORT_DURATION_SECONDS = 28
DEFAULT_SHORT_SENTENCE_COUNT = 3

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
        'learning_note': '',
        'topic': '',
        'scene': 'travel'
    }
    
    if not message or not message.strip():
        return result
    
    message = message.strip()
    
    # 尝试提取主题/场景
    if '：' in message or ':' in message:
        parts = message.split('：' if '：' in message else ':', 1)
        if len(parts) == 2:
            topic_part = parts[0].strip()
            content_part = parts[1].strip()
            
            # 判断是否是场景描述
            scene_keywords = ['酒店', '旅行', '机场', '餐厅', '购物', '医院', '银行', '办公室', '商务', '亲子', '救场', '生活']
            if any(kw in topic_part for kw in scene_keywords):
                result['topic'] = topic_part
                result['learning_note'] = content_part
                result['scene'] = _detect_scene(topic_part)
            else:
                result['learning_note'] = message
        else:
            result['learning_note'] = message
    else:
        result['learning_note'] = message
        result['scene'] = _detect_scene(message)
    
    return result


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
        workflow = create_workflow()
        
        # 构建工作流输入
        workflow_input = {
            'learning_note': user_input.get('learning_note', ''),
            'topic': user_input.get('topic', ''),
            'scene': user_input.get('scene', 'travel'),
            'duration_seconds': DEFAULT_SHORT_DURATION_SECONDS,
            'sentence_count': DEFAULT_SHORT_SENTENCE_COUNT,
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


def agent_node(state: MessagesState) -> Dict[str, Any]:
    """
    Agent 节点：处理用户消息并生成视频
    
    流程：
    1. 接收用户的聊天消息
    2. 解析用户输入，提取学习内容
    3. 调用工作流图生成视频
    4. 返回视频生成结果
    """
    import asyncio
    
    messages = state.get('messages', [])
    
    # 获取最后一条用户消息
    user_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
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
        workflow = create_workflow()
        
        # 构建工作流输入
        workflow_input = {
            'learning_note': user_input.get('learning_note', ''),
            'topic': user_input.get('topic', ''),
            'scene': user_input.get('scene', 'travel'),
            'duration_seconds': DEFAULT_SHORT_DURATION_SECONDS,
            'sentence_count': DEFAULT_SHORT_SENTENCE_COUNT,
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
    
    if draft_url:
        response += f"剪映草稿链接：{draft_url}\n"
    
    # 添加视频内容摘要
    segments = result.get('segments', [])
    if segments:
        response += f"\n视频包含 {len(segments)} 个片段：\n"
        for i, seg in enumerate(segments[:3], 1):
            subtitle = seg.get('subtitle', '')
            if subtitle:
                response += f"{i}. {subtitle[:50]}...\n" if len(subtitle) > 50 else f"{i}. {subtitle}\n"
    
    response += "\n请在剪映中打开草稿链接进行编辑和导出。"
    
    return {
        'messages': [AIMessage(content=response)]
    }


def build_agent(ctx=None) -> CompiledStateGraph:
    """
    构建聊天 Agent
    
    这个 Agent 能够：
    1. 接收用户的聊天消息
    2. 解析用户输入，提取学习内容
    3. 调用视频生成工作流
    4. 返回视频生成结果
    """
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
