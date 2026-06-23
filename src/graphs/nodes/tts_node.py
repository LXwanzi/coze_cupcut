"""
TTS 配音节点
输入: video_plan
输出: audio_url
"""
import logging
from typing import Dict, Any
from coze_coding_dev_sdk import TTSClient
from coze_coding_utils.runtime_ctx.context import new_context

logger = logging.getLogger(__name__)


def tts_synthesize(state: Dict[str, Any]) -> Dict[str, Any]:
    """调用 TTS 生成配音"""
    ctx = new_context(method="tts_synthesize")
    client = TTSClient(ctx=ctx)
    
    video_plan = state.get("video_plan")
    if not video_plan:
        return {
            "audio_url": None,
            "error": "缺少 video_plan，无法生成配音"
        }
    
    voice_text = video_plan.get("voice_text", "")
    if not voice_text:
        return {
            "audio_url": None,
            "error": "video_plan 中缺少 voice_text"
        }
    
    try:
        audio_url, audio_size = client.synthesize(
            uid="capcut-video-generator",
            text=voice_text,
            speaker="zh_female_xiaohe_uranus_bigtts",
            audio_format="mp3",
            sample_rate=24000
        )
        
        logger.info(f"TTS generated: {audio_url}, size: {audio_size}")
        
        return {
            "audio_url": audio_url,
            "audio_size": audio_size,
            "error": None
        }
        
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return {
            "audio_url": None,
            "error": f"TTS 生成失败: {str(e)}"
        }
