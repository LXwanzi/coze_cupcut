"""
剪映草稿生成工作流图
"""
import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END

from graphs.nodes.generate_plan import generate_plan
from graphs.nodes.tts_node import tts_synthesize
from graphs.nodes.image_gen_node import generate_images
from graphs.nodes.capcut_node import create_capcut_draft

logger = logging.getLogger(__name__)


class VideoWorkflowState(dict):
    """工作流状态"""
    topic: str
    duration_seconds: int
    style: str
    canvas_width: int
    canvas_height: int
    video_plan: Dict[str, Any]
    audio_url: str
    audio_size: int
    scenes_generated: int
    success: bool
    draft_url: str
    duration: int
    scene_count: int
    caption_count: int
    error: str


def create_workflow() -> StateGraph:
    """创建工作流图"""
    
    workflow = StateGraph(VideoWorkflowState)
    
    # 添加节点
    workflow.add_node("generate_plan", generate_plan_node)
    workflow.add_node("tts_synthesize", tts_synthesize_node)
    workflow.add_node("generate_images", generate_images_node)
    workflow.add_node("create_capcut_draft", create_capcut_draft_node)
    
    # 设置入口点
    workflow.set_entry_point("generate_plan")
    
    # 添加边
    workflow.add_edge("generate_plan", "tts_synthesize")
    workflow.add_edge("tts_synthesize", "generate_images")
    workflow.add_edge("generate_images", "create_capcut_draft")
    workflow.add_edge("create_capcut_draft", END)
    
    return workflow.compile()


def generate_plan_node(state: VideoWorkflowState) -> Dict[str, Any]:
    """生成视频计划节点"""
    from graphs.nodes.generate_plan import generate_plan
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


def tts_synthesize_node(state: VideoWorkflowState) -> Dict[str, Any]:
    """TTS 配音节点"""
    from graphs.nodes.tts_node import tts_synthesize
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


def generate_images_node(state: VideoWorkflowState) -> Dict[str, Any]:
    """AI 图片生成节点"""
    from graphs.nodes.image_gen_node import generate_images
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


def create_capcut_draft_node(state: VideoWorkflowState) -> Dict[str, Any]:
    """CapCut API 调用节点"""
    from graphs.nodes.capcut_node import create_capcut_draft
    result = create_capcut_draft(state)
    
    return {
        "success": result.get("success", False),
        "draft_url": result.get("draft_url"),
        "duration": result.get("duration"),
        "scene_count": result.get("scene_count"),
        "caption_count": result.get("caption_count"),
        "error": result.get("error")
    }


# 全局工作流实例
_workflow = None


def get_graph() -> StateGraph:
    """获取工作流图实例"""
    global _workflow
    if _workflow is None:
        _workflow = create_workflow()
    return _workflow


def build_graph():
    """构建工作流图（兼容主程序接口）"""
    return get_graph()
