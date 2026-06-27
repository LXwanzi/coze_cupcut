"""
TTS 配音节点
输入: segments, content_meta, video_plan
输出: audio_segments, audio_url, total_duration

为每个片段单独生成音频，获取实际时长，确保音视频同步。
支持多种音色选择（见 TTS_VOICES 配置）。
"""

import logging
import time
import wave
import os
from typing import Dict, Any, List, Optional
import requests
from coze_coding_dev_sdk import TTSClient
from coze_coding_utils.runtime_ctx.context import new_context
from graphs.nodes.oss_uploader import upload_audio_to_oss

# ========== TTS 音色配置 ==========
# 可选音色：
# - zh_female_xiaohe_uranus_bigtts (小禾 - 默认，通用女声)
# - zh_female_vv_uranus_bigtts (Vivi - 中英双语)
# - zh_female_xueayi_saturn_bigtts (雪球 - 儿童故事)
# - zh_male_m191_uranus_bigtts (云舟 - 男声)
# - zh_male_taocheng_uranus_bigtts (小天 - 男声)
# - zh_male_dayi_saturn_bigtts (大奕 - 视频配音男声)
# - zh_female_mizai_saturn_bigtts (米仔 - 视频配音女声)
# - zh_female_meilinvyou_saturn_bigtts (美丽女友 - 商务女声)
# - zh_female_santongyongns_saturn_bigtts (三通女 - 温柔女声)
# - zh_male_ruyayichen_saturn_bigtts (儒雅男 - 优雅男声)
# - saturn_zh_female_keainvsheng_tob (可爱女声)
# - saturn_zh_female_tiaopigongzhu_tob (俏皮女声)
# - saturn_zh_male_shuanglangshaonian_tob (爽朗少年)
# - saturn_zh_male_tiancaitongzhuo_tob (天才同学)
# - saturn_zh_female_cancan_tob (才女)

TTS_VOICES = {
    "default": "ICL_uranus_en_female_charlie_tob",
    "xiaohao": "zh_female_xiaohe_uranus_bigtts",
    "vivi": "zh_female_vv_uranus_bigtts",
    "children": "zh_female_xueayi_saturn_bigtts",
    "parent_child": "zh_female_xueayi_saturn_bigtts",
    "kids": "zh_female_xueayi_saturn_bigtts",
    "male": "zh_male_m191_uranus_bigtts",
    "yunzhou": "zh_male_m191_uranus_bigtts",
    "xiaotian": "zh_male_taocheng_uranus_bigtts",
    "business": "zh_female_meilinvyou_saturn_bigtts",
    "bec": "zh_female_meilinvyou_saturn_bigtts",
    "professional": "zh_female_meilinvyou_saturn_bigtts",
    "video": "zh_male_dayi_saturn_bigtts",
    "dubbing": "zh_female_mizai_saturn_bigtts",
    "motivation": "zh_female_jitangnv_saturn_bigtts",
    "gentle": "zh_female_santongyongns_saturn_bigtts",
    "sweet": "zh_female_santongyongns_saturn_bigtts",
    "elegant": "zh_male_ruyayichen_saturn_bigtts",
    "cute": "saturn_zh_female_keainvsheng_tob",
    "playful": "saturn_zh_female_tiaopigongzhu_tob",
    "cheerful": "saturn_zh_male_shuanglangshaonian_tob",
    "genius": "saturn_zh_male_tiancaitongzhuo_tob",
    "smart": "saturn_zh_female_cancan_tob",
}

DEFAULT_VOICE = "ICL_uranus_en_female_charlie_tob"
# 短视频默认要更利落。若底层 TTS SDK 不支持 speed 参数，也会靠更短文案控时长。
TTS_SPEED = float(os.getenv("TTS_SPEED", "1.05"))
TARGET_TOTAL_DURATION_SECONDS = float(os.getenv("TARGET_TOTAL_DURATION_SECONDS", "28"))
# =================================

logger = logging.getLogger(__name__)

CAPCUT_MATE_BASE_URL = os.getenv(
    "CAPCUT_MATE_BASE_URL",
    "http://123.57.144.37:30000/openapi/capcut-mate/v1"
)
MICROSECONDS_PER_SECOND = 1_000_000


def _seconds_to_us(seconds: float) -> int:
    return max(1, int(round(seconds * MICROSECONDS_PER_SECOND)))


def _resolve_voice_and_speed(content_meta: Dict[str, Any]) -> tuple[str, float]:
    """Resolve configured voice profile into concrete TTS speaker and speed."""
    content_meta = content_meta or {}
    voice_profile = content_meta.get("voice_profile") or {}
    voice_key = (
        voice_profile.get("voice") or
        content_meta.get("voice") or
        content_meta.get("scene") or
        "default"
    )
    scene = content_meta.get("scene")
    if scene == "parent_child" and "voice" not in voice_profile:
        voice_key = "parent_child"
    elif scene in ["business", "bec"] and "voice" not in voice_profile:
        voice_key = "business"

    try:
        speed = float(voice_profile.get("speed", TTS_SPEED))
    except (TypeError, ValueError):
        speed = TTS_SPEED
    speed = max(0.8, min(speed, 1.3))
    return TTS_VOICES.get(voice_key, DEFAULT_VOICE), speed


def _get_audio_duration_from_capcut(mp3_url: str) -> Optional[int]:
    """通过 capcut-mate 获取音频时长，返回微秒。"""
    try:
        response = requests.post(
            f"{CAPCUT_MATE_BASE_URL}/get_audio_duration",
            json={"mp3_url": mp3_url},
            timeout=60
        )
        data = response.json()
        duration = data.get("duration") or data.get("data", {}).get("duration")
        if data.get("code") == 0 and duration:
            return int(duration)
        if duration and "code" not in data:
            return int(duration)
        logger.warning(f"capcut audio duration failed: {data}")
    except Exception as e:
        logger.warning(f"Failed to get audio duration from capcut-mate: {e}")
    return None


def _get_audio_duration(file_path: str) -> float:
    """获取音频文件时长（秒）"""
    try:
        if file_path.startswith('http'):
            # 下载到临时文件
            import urllib.request
            temp_path = f"/tmp/tts_check_{int(time.time())}.mp3"
            urllib.request.urlretrieve(file_path, temp_path)
            file_path = temp_path
        
        # 尝试使用 mutagen 读取 mp3 时长
        try:
            from mutagen.mp3 import MP3
            audio = MP3(file_path)
            duration = audio.info.length
        except ImportError:
            # 如果没有 mutagen，尝试用 wave（用于 wav 格式）
            if file_path.endswith('.wav'):
                with wave.open(file_path, 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    duration = frames / float(rate)
            else:
                # 无法读取，返回估算值
                duration = None
        
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
    ctx,
    speed: float = TTS_SPEED
) -> Optional[Dict[str, Any]]:
    """为单个片段生成音频"""
    try:
        # 清理临时文件名中的空格
        safe_uid = f"segment_{segment_index}_{int(time.time())}".replace(" ", "_")
        
        synthesize_kwargs = {
            "uid": safe_uid,
            "text": text,
            "speaker": speaker,
            "audio_format": "mp3",
            "sample_rate": 24000,
        }
        if speed:
            synthesize_kwargs["speed"] = speed

        try:
            audio_url, audio_size = client.synthesize(**synthesize_kwargs)
        except TypeError:
            # Some Coze runtimes do not expose speed control on TTSClient yet.
            synthesize_kwargs.pop("speed", None)
            audio_url, audio_size = client.synthesize(**synthesize_kwargs)
        
        # 上传到 OSS
        oss_url = upload_audio_to_oss(audio_url)
        final_url = oss_url if oss_url else audio_url

        # 优先让 capcut-mate 用 ffprobe 读取最终 URL，避免本地缺 mutagen 时靠字符数估算。
        duration_us = _get_audio_duration_from_capcut(final_url)
        if duration_us is None:
            duration = _get_audio_duration(audio_url)
            if duration is None:
                # 最后兜底：估算时长。只在远端接口和本地探测都失败时使用。
                duration = max(1.5, len(text) / 4.0)
            duration_us = _seconds_to_us(duration)
        duration = duration_us / MICROSECONDS_PER_SECOND
        
        logger.info(
            f"Segment {segment_index} audio: {final_url}, "
            f"duration: {duration:.2f}s ({duration_us} μs)"
        )
        
        return {
            "url": final_url,
            "duration": duration_us,
            "duration_seconds": duration,
            "duration_us": duration_us,
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
        
        # 获取音色配置：优先使用用户指定的音色，其次根据场景选择
        speaker, speed = _resolve_voice_and_speed(state.get("content_meta", {}))
        
        try:
            synthesize_kwargs = {
                "uid": "english-content-assistant",
                "text": voice_text,
                "speaker": speaker,
                "audio_format": "mp3",
                "sample_rate": 24000,
                "speed": speed,
            }
            try:
                audio_url, audio_size = client.synthesize(**synthesize_kwargs)
            except TypeError:
                synthesize_kwargs.pop("speed", None)
                audio_url, audio_size = client.synthesize(**synthesize_kwargs)
            
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
    
    # 根据内容模式选择音色和语速
    speaker, speed = _resolve_voice_and_speed(state.get("content_meta", {}))
    
    # 为每个片段生成音频
    audio_segments = []
    current_time_us = 0
    
    for i, segment in enumerate(segments):
        if not segment or not isinstance(segment, dict):
            logger.warning(f"Segment {i} is invalid, skipping: {segment}")
            continue
        
        tts_text = segment.get("tts", "")
        if not tts_text:
            continue
        
        result = _generate_segment_audio(client, tts_text, speaker, i, ctx, speed=speed)
        
        if result:
            duration_us = int(result["duration_us"])
            start_us = current_time_us
            end_us = start_us + duration_us
            audio_segments.append({
                "index": i,
                "scene": segment.get("scene", ""),
                "tts_text": tts_text,
                "caption": segment.get("caption", ""),
                "audio_url": result["url"],  # 统一使用 audio_url
                "duration": duration_us,
                "duration_seconds": result["duration_seconds"],
                "start": start_us,
                "end": end_us,
                "scene_data": segment  # 保留原始片段数据
            })
            current_time_us = end_us
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
    
    total_duration = current_time_us
    target_duration_us = int(
        state.get("content_meta", {}).get("target_duration_seconds", TARGET_TOTAL_DURATION_SECONDS)
        * MICROSECONDS_PER_SECOND
    )
    if total_duration > target_duration_us:
        logger.warning(
            "TTS total duration %.2fs exceeds target %.2fs; shorten generated TTS text or reduce sentence_count.",
            total_duration / MICROSECONDS_PER_SECOND,
            target_duration_us / MICROSECONDS_PER_SECOND,
        )
    
    logger.info(
        f"TTS completed: {len(audio_segments)} segments, "
        f"total_duration: {total_duration / MICROSECONDS_PER_SECOND:.2f}s"
    )
    
    return {
        "audio_url": audio_segments[0]["audio_url"] if audio_segments else None,  # 保留第一个片段 URL
        "audio_segments": audio_segments,
        "total_duration": total_duration,
        "error": None
    }
