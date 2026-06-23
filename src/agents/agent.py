"""
剪映草稿生成 Agent
使用工作流图来生成剪映草稿
"""
import os
import json
import logging
from typing import Annotated
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph
from coze_coding_utils.runtime_ctx.context import default_headers
from storage.memory.memory_saver import get_memory_saver
from graphs.nodes.generate_plan import generate_plan
from graphs.nodes.tts_node import tts_synthesize
from graphs.nodes.image_gen_node import generate_images
from graphs.nodes.capcut_node import create_capcut_draft

logger = logging.getLogger(__name__)

LLM_CONFIG = "config/agent_llm_config.json"

# 默认保留最近 20 轮对话 (40 条消息)
MAX_MESSAGES = 40


def _windowed_messages(old, new):
    """滑动窗口: 只保留最近 MAX_MESSAGES 条消息"""
    return list(add_messages(old, new))[-MAX_MESSAGES:]


class AgentState(MessagesState):
    """Agent 状态"""
    topic: str
    duration_seconds: int
    style: str
    canvas_width: int
    canvas_height: int
    video_plan: dict
    audio_url: str
    audio_size: int
    scenes_generated: int
    success: bool
    draft_url: str
    duration: int
    scene_count: int
    caption_count: int
    error: str
    messages: Annotated[list[AnyMessage], _windowed_messages]


def _generate_plan_node(state: AgentState) -> dict:
    """生成视频计划节点"""
    result = generate_plan(state)

    if result.get("error"):
        return {
            "error": result["error"],
            "success": False
        }

    return {
        "video_plan": result.get("video_plan"),
        "error": None
    }


def _tts_node(state: AgentState) -> dict:
    """TTS 配音节点"""
    result = tts_synthesize(state)

    if result.get("error"):
        return {
            "error": result["error"],
            "success": False
        }

    return {
        "audio_url": result.get("audio_url"),
        "audio_size": result.get("audio_size"),
        "error": None
    }


def _generate_images_node(state: AgentState) -> dict:
    """AI 图片生成节点"""
    result = generate_images(state)

    if result.get("error"):
        return {
            "error": result["error"],
            "success": False
        }

    return {
        "video_plan": result.get("video_plan"),
        "scenes_generated": result.get("scenes_generated", 0),
        "errors": result.get("errors"),
        "error": None
    }


def _capcut_node(state: AgentState) -> dict:
    """CapCut API 调用节点"""
    result = create_capcut_draft(state)

    return {
        "success": result.get("success", False),
        "draft_url": result.get("draft_url"),
        "duration": result.get("duration"),
        "scene_count": result.get("scene_count"),
        "caption_count": result.get("caption_count"),
        "error": result.get("error")
    }


def _create_workflow():
    """创建工作流图"""
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("generate_plan", _generate_plan_node)
    workflow.add_node("tts_synthesize", _tts_node)
    workflow.add_node("generate_images", _generate_images_node)
    workflow.add_node("create_capcut_draft", _capcut_node)

    # 设置入口点
    workflow.set_entry_point("generate_plan")

    # 添加边
    workflow.add_edge("generate_plan", "tts_synthesize")
    workflow.add_edge("tts_synthesize", "generate_images")
    workflow.add_edge("generate_images", "create_capcut_draft")
    workflow.add_edge("create_capcut_draft", END)

    return workflow


class AgentBuilder:
    """Agent 构建器"""

    def __init__(self):
        self.builder = _create_workflow()


def build_agent(ctx=None):
    """构建 Agent"""
    return AgentBuilder()
