"""
TTS 配音节点
输入: voice_text
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

    # 优先使用 voice_text
    voice_text = state.get("voice_text")
    if not voice_text:
        # 兼容旧格式
        video_plan = state.get("video_plan")
        if video_plan:
            voice_text = video_plan.get("voice_text", "")

    if not voice_text:
        return {
            "audio_url": None,
            "error": "缺少 voice_text，无法生成配音"
        }

    # 根据场景选择音色
    scene = state.get("content_meta", {}).get("scene", "commute")
    if scene == "parent_child":
        speaker = "zh_female_xueayi_saturn_bigtts"  # 亲子场景用儿童音色
    elif scene == "business" or scene == "bec":
        speaker = "zh_female_meilinvyou_saturn_bigtts"  # 商务场景用专业女声
    else:
        speaker = "zh_female_xiaohe_uranus_bigtts"  # 默认通勤场景

    try:
        audio_url, audio_size = client.synthesize(
            uid="english-content-assistant",
            text=voice_text,
            speaker=speaker,
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
