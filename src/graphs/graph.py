"""
剪映草稿生成工作流图 - 音频同步版
"""
import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from graphs.nodes.generate_plan import generate_plan
from graphs.nodes.tts_node import tts_synthesize
from graphs.nodes.image_gen_node import generate_images
from graphs.nodes.capcut_node import create_capcut_draft

logger = logging.getLogger(__name__)


class VideoWorkflowState(dict):
    """工作流状态"""
    # 输入字段
    account_id: str
    raw_topic: str
    learning_note: str
    topic: str
    scene: str
    auto_generate_expressions: bool
    content_mode: str
    voice_profile_override: Dict[str, Any]
    duration_seconds: int
    sentence_count: int
    audience: str
    tone: str
    canvas_width: int
    canvas_height: int
    
    # 中间状态
    topic_id: str  # 专题ID
    episode_info: Dict[str, Any]  # 集数信息
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
    output_dir: str
    output_files: Dict[str, Any]
    timeline_segments: list
    error: str


def create_workflow() -> CompiledStateGraph:
    """创建工作流图"""
    
    workflow = StateGraph(VideoWorkflowState)
    
    # 添加节点
    workflow.add_node("generate_plan", generate_plan_node)
    workflow.add_node("tts_synthesize", tts_synthesize_node)
    workflow.add_node("generate_images", generate_images_node)
    workflow.add_node("create_capcut_draft", create_capcut_draft_node)
    
    # 设置入口点
    workflow.set_entry_point("generate_plan")
    
    # 添加条件边：出错时直接结束
    workflow.add_conditional_edges(
        "generate_plan",
        _check_error,
        {
            "continue": "tts_synthesize",
            "error": END
        }
    )
    workflow.add_conditional_edges(
        "tts_synthesize",
        _check_error,
        {
            "continue": "generate_images",
            "error": END
        }
    )
    workflow.add_conditional_edges(
        "generate_images",
        _check_error,
        {
            "continue": "create_capcut_draft",
            "error": END
        }
    )
    workflow.add_edge("create_capcut_draft", END)
    
    return workflow.compile()


def _check_error(state: VideoWorkflowState) -> str:
    """检查状态中是否有错误，决定继续还是结束"""
    if state.get("error"):
        return "error"
    return "continue"


def generate_plan_node(state: VideoWorkflowState) -> Dict[str, Any]:
    """生成视频计划节点"""
    result = generate_plan(state)
    
    if result.get("error"):
        return {
            "error": result["error"],
            "success": False,
            "video_plan": result.get("video_plan", {})
        }
    
    return {
        "topic_id": result.get("topic_id"),
        "account_id": state.get("account_id"),
        "content_meta": result.get("content_meta"),
        "publish_pack": result.get("publish_pack"),
        "review_card": result.get("review_card"),
        "episode_info": result.get("episode_info"),
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
            "success": False,
            "video_plan": state.get("video_plan", {})
        }
    
    # 将音频信息合并到 segments 中
    audio_segments = result.get("audio_segments", [])
    segments = state.get("segments", [])
    
    # 更新每个 segment 的音频 URL 和时长
    for i, seg in enumerate(segments):
        if not seg:
            continue
        for audio_seg in audio_segments:
            if not audio_seg:
                continue
            if audio_seg.get("index") == i:
                seg["audio_url"] = audio_seg.get("audio_url") or audio_seg.get("url")
                seg["audio_duration"] = audio_seg.get("duration")
                seg["audio_duration_seconds"] = audio_seg.get("duration_seconds")
                seg["start"] = audio_seg.get("start")
                seg["end"] = audio_seg.get("end")
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
            "success": False,
            "video_plan": state.get("video_plan", {})
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
    
    # 更新 segments 和 audio_segments 中的场景信息。后续 CapCut 节点只使用同一套
    # audio_segments 时间轴，避免图片/字幕/音频各自生成时间导致错位。
    for i, seg in enumerate(segments):
        if i < len(scenes):
            scene = scenes[i]
            seg["asset_url"] = scene.get("asset_url")
            seg["image_url"] = scene.get("asset_url")

    audio_segments = state.get("audio_segments", [])
    for audio_seg in audio_segments:
        index = audio_seg.get("index")
        if isinstance(index, int) and index < len(scenes):
            scene = scenes[index]
            audio_seg["asset_url"] = scene.get("asset_url")
            audio_seg["image_url"] = scene.get("asset_url")
            audio_seg["image_prompt"] = scene.get("prompt", "")
        if isinstance(index, int) and index < len(segments):
            audio_seg["scene_data"] = segments[index]
    
    return {
        "scenes": scenes,
        "video_plan": video_plan,
        "segments": segments,
        "audio_segments": audio_segments,
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
        "segments": result.get("segments", state.get("segments", [])),
        "timeline_segments": result.get("timeline_segments", []),
        "output_dir": result.get("output_dir"),
        "output_files": result.get("output_files", {}),
        "steps_status": result.get("steps_status", []),
        "message": result.get("message"),
        "error": result.get("error")
    }


# 全局工作流实例
#
# coze_coding_utils.helper.graph_helper.get_graph_instance() 不会调用
# build_graph()，只会扫描模块里的 CompiledStateGraph 对象。因此这里必须在
# 模块加载时暴露一个已编译图，否则 workflow 模式下会拿到 None。
graph = create_workflow()
_workflow = graph


def get_graph() -> CompiledStateGraph:
    """获取工作流图实例"""
    return _workflow


def build_graph():
    """构建工作流图（兼容主程序接口）"""
    return get_graph()
