"""
剪映草稿生成工作流图 - 音频同步版
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
    # 输入字段
    learning_note: str
    scene: str
    duration_seconds: int
    audience: str
    tone: str
    canvas_width: int
    canvas_height: int
    
    # 中间状态
    content_meta: Dict[str, Any]
    publish_pack: Dict[str, Any]
    review_card: Dict[str, Any]
    voice_text: str
    segments: list  # 结构化片段数据
    video_plan: Dict[str, Any]
    
    # TTS 输出
    audio_url: str
    audio_size: int
    audio_segments: list  # 片段级音频（带时长）
    total_duration: float
    
    # 图片生成输出
    scenes: list  # 包含 asset_url 的 scenes
    
    # CapCut 输出
    success: bool
    draft_url: str
    steps_status: list
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
    result = generate_plan(state)
    
    if result.get("error"):
        return {
            "error": result["error"],
            "success": False
        }
    
    return {
        "content_meta": result.get("content_meta"),
        "publish_pack": result.get("publish_pack"),
        "review_card": result.get("review_card"),
        "voice_text": result.get("voice_text"),
        "segments": result.get("segments", []),
        "video_plan": result.get("video_plan"),
        "material_bank": result.get("material_bank", []),
        "error": None
    }


def tts_synthesize_node(state: VideoWorkflowState) -> Dict[str, Any]:
    """TTS 配音节点 - 为每个片段生成音频"""
    result = tts_synthesize(state)
    
    if result.get("error"):
        return {
            "error": result["error"],
            "success": False
        }
    
    # 将音频信息合并到 segments 中
    audio_segments = result.get("audio_segments", [])
    segments = state.get("segments", [])
    
    # 更新每个 segment 的音频 URL 和时长
    for i, seg in enumerate(segments):
        for audio_seg in audio_segments:
            if audio_seg.get("index") == i:
                seg["audio_url"] = audio_seg.get("url")
                seg["audio_duration"] = audio_seg.get("duration")
                break
    
    return {
        "audio_url": result.get("audio_url"),
        "audio_segments": audio_segments,
        "total_duration": result.get("total_duration"),
        "segments": segments,
        "error": None
    }


def generate_images_node(state: VideoWorkflowState) -> Dict[str, Any]:
    """AI 图片生成节点 - 为每个片段生成图片"""
    result = generate_images(state)
    
    if result.get("error"):
        return {
            "error": result["error"],
            "success": False
        }
    
    # 获取生成的 scenes
    scenes = result.get("scenes", [])
    
    # 将图片信息合并到 segments 中
    segments = state.get("segments", [])
    video_plan = state.get("video_plan", {})
    
    # 更新 video_plan 中的 scenes
    video_plan_scenes = video_plan.get("scenes", [])
    for i, scene in enumerate(scenes):
        if i < len(video_plan_scenes):
            video_plan_scenes[i]["asset_url"] = scene.get("asset_url")
    
    # 更新 segments 中的场景信息
    for i, seg in enumerate(segments):
        for scene in scenes:
            if scene.get("visual_role") == seg.get("scene") or i == scenes.index(scene):
                seg["asset_url"] = scene.get("asset_url")
                seg["image_url"] = scene.get("asset_url")
                break
    
    return {
        "scenes": scenes,
        "video_plan": video_plan,
        "segments": segments,
        "error": None
    }


def create_capcut_draft_node(state: VideoWorkflowState) -> Dict[str, Any]:
    """CapCut API 调用节点 - 基于音频时间轴生成草稿"""
    result = create_capcut_draft(state)
    
    return {
        "success": result.get("success", False),
        "draft_url": result.get("draft_url"),
        "content_meta": result.get("content_meta"),
        "publish_pack": result.get("publish_pack"),
        "review_card": result.get("review_card"),
        "material_bank": result.get("material_bank", []),
        "steps_status": result.get("steps_status", []),
        "message": result.get("message"),
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
