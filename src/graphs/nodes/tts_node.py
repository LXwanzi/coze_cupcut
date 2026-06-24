"""
TTS 配音节点
输入: segments, content_meta, video_plan
输出: audio_segments, audio_url, total_duration

为每个片段单独生成音频，获取实际时长，确保音视频同步。
"""
import logging
import json
import time
import wave
import os
from typing import Dict, Any, List, Optional
from coze_coding_dev_sdk import TTSClient
from coze_coding_utils.runtime_ctx.context import new_context
from graphs.nodes.oss_uploader import upload_audio_to_oss, _get_bucket
import oss2

logger = logging.getLogger(__name__)


def _get_audio_duration(file_path: str) -> float:
    """获取音频文件时长（秒）"""
    try:
        if file_path.startswith('http'):
            # 下载到临时文件
            import urllib.request
            temp_path = f"/tmp/tts_check_{int(time.time())}.mp3"
            urllib.request.urlretrieve(file_path, temp_path)
            file_path = temp_path
        
        # 使用 wave 模块获取时长
        with wave.open(file_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            duration = frames / float(rate)
        
        # 清理临时文件
        if file_path.startswith('/tmp/'):
            try:
                os.remove(file_path)
            except:
                pass
        
        return duration
    except Exception as e:
        logger.warning(f"Failed to get audio duration: {e}")
        # 估算：中文约 4-6 字/秒，英文约 2-3 字/秒
        return None


def _generate_segment_audio(
    client: TTSClient,
    text: str,
    speaker: str,
    segment_index: int,
    ctx
) -> Optional[Dict[str, Any]]:
    """为单个片段生成音频"""
    try:
        audio_url, audio_size = client.synthesize(
            uid=f"segment_{segment_index}_{int(time.time())}",
            text=text,
            speaker=speaker,
            audio_format="wav",  # 使用 wav 以便获取时长
            sample_rate=24000
        )
        
        # 获取音频时长
        duration = _get_audio_duration(audio_url)
        if duration is None:
            # 估算时长：约 3-5 字/秒
            duration = max(1.5, len(text) / 4.0)
        
        # 上传到 OSS
        oss_url = upload_audio_to_oss(audio_url)
        final_url = oss_url if oss_url else audio_url
        
        logger.info(f"Segment {segment_index} audio: {final_url}, duration: {duration:.2f}s")
        
        return {
            "url": final_url,
            "duration": duration,
            "original_url": audio_url
        }
        
    except Exception as e:
        logger.error(f"Segment {segment_index} audio error: {e}")
        return None


def tts_synthesize(state: Dict[str, Any]) -> Dict[str, Any]:
    """调用 TTS 生成配音，为每个片段单独生成"""
    ctx = new_context(method="tts_synthesize")
    client = TTSClient(ctx=ctx)

    segments = state.get("segments", [])
    
    # 如果没有 segments，使用旧的 voice_text 方式
    if not segments:
        voice_text = state.get("voice_text")
        if not voice_text:
            video_plan = state.get("video_plan")
            if video_plan:
                voice_text = video_plan.get("voice_text", "")
        
        if not voice_text:
            return {
                "audio_url": None,
                "audio_segments": [],
                "total_duration": 0,
                "error": "缺少 voice_text，无法生成配音"
            }
        
        # 使用旧方式生成整段音频
        scene = state.get("content_meta", {}).get("scene", "commute")
        if scene == "parent_child":
            speaker = "zh_female_xueayi_saturn_bigtts"
        elif scene == "business" or scene == "bec":
            speaker = "zh_female_meilinvyou_saturn_bigtts"
        else:
            speaker = "zh_female_xiaohe_uranus_bigtts"
        
        try:
            audio_url, audio_size = client.synthesize(
                uid="english-content-assistant",
                text=voice_text,
                speaker=speaker,
                audio_format="mp3",
                sample_rate=24000
            )
            
            oss_url = upload_audio_to_oss(audio_url)
            final_url = oss_url if oss_url else audio_url
            
            logger.info(f"TTS generated (legacy): {final_url}")
            
            return {
                "audio_url": final_url,
                "audio_segments": [],
                "total_duration": None,
                "error": None
            }
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return {
                "audio_url": None,
                "audio_segments": [],
                "total_duration": 0,
                "error": f"TTS 生成失败: {str(e)}"
            }
    
    # 根据场景选择音色
    scene = state.get("content_meta", {}).get("scene", "commute")
    if scene == "parent_child":
        speaker = "zh_female_xueayi_saturn_bigtts"
    elif scene == "business" or scene == "bec":
        speaker = "zh_female_meilinvyou_saturn_bigtts"
    else:
        speaker = "zh_female_xiaohe_uranus_bigtts"
    
    # 为每个片段生成音频
    audio_segments = []
    current_time = 0.0
    
    for i, segment in enumerate(segments):
        tts_text = segment.get("tts", "")
        if not tts_text:
            continue
        
        result = _generate_segment_audio(client, tts_text, speaker, i, ctx)
        
        if result:
            duration = result["duration"]
            audio_segments.append({
                "index": i,
                "scene": segment.get("scene", ""),
                "tts_text": tts_text,
                "caption": segment.get("caption", ""),
                "audio_url": result["url"],  # 统一使用 audio_url
                "duration": duration,
                "start": current_time,
                "end": current_time + duration,
                "scene_data": segment  # 保留原始片段数据
            })
            current_time += duration
        else:
            # 生成失败，跳过该片段
            logger.warning(f"Skipping segment {i} due to audio generation failure")
    
    if not audio_segments:
        return {
            "audio_url": None,
            "audio_segments": [],
            "total_duration": 0,
            "error": "所有片段音频生成失败"
        }
    
    total_duration = current_time
    
    logger.info(f"TTS completed: {len(audio_segments)} segments, total_duration: {total_duration:.2f}s")
    
    return {
        "audio_url": audio_segments[0]["url"] if audio_segments else None,  # 保留第一个片段 URL
        "audio_segments": audio_segments,
        "total_duration": total_duration,
        "error": None
    }
