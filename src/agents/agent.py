"""
通勤英语内容助手 Agent
把每日英语学习笔记转化为原创短视频内容
"""
import os
import json
import logging
from typing import Annotated
from langgraph.graph import MessagesState, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
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
    # 输入字段
    learning_note: str
    scene: str
    duration_seconds: int
    audience: str
    tone: str
    canvas_width: int
    canvas_height: int

    # 内容生成结果
    content_meta: dict
    publish_pack: dict
    voice_text: str
    review_card: dict
    video_plan: dict
    material_bank: list
    scenes: list  # 包含 asset_url 的 scenes

    # 媒体生成结果
    audio_url: str
    audio_size: int
    scenes_generated: int

    # CapCut API 结果
    steps_status: list

    # 最终结果
    success: bool
    draft_url: str
    error: str

    # 消息历史
    messages: Annotated[list[AnyMessage], _windowed_messages]


def _generate_plan_node(state: AgentState) -> dict:
    """生成内容计划节点"""
    result = generate_plan(state)

    if result.get("error"):
        return {
            "error": result["error"],
            "success": False
        }

    return {
        "content_meta": result.get("content_meta"),
        "publish_pack": result.get("publish_pack"),
        "voice_text": result.get("voice_text"),
        "review_card": result.get("review_card"),
        "video_plan": result.get("video_plan"),
        "material_bank": result.get("material_bank", []),
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

    # 更新 video_plan 中的 scenes
    video_plan = state.get("video_plan", {})
    updated_scenes = result.get("scenes", [])
    video_plan["scenes"] = updated_scenes

    return {
        "video_plan": video_plan,
        "scenes": updated_scenes,
        "scenes_generated": len(updated_scenes),
        "error": None
    }


def _capcut_node(state: AgentState) -> dict:
    """CapCut API 调用节点"""
    result = create_capcut_draft(state)

    return {
        "success": result.get("success", False),
        "draft_url": result.get("draft_url"),
        "title": result.get("publish_pack", {}).get("title"),
        "cover_text": result.get("publish_pack", {}).get("cover_text"),
        "review_card": result.get("review_card"),
        "material_bank": result.get("material_bank"),
        "steps_status": result.get("steps_status", []),
        "error": result.get("error"),
        "message": result.get("message")
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
