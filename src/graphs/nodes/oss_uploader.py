"""OSS 图片上传工具"""

import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# OSS 配置
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "https://oss-cn-beijing.aliyuncs.com")
OSS_BUCKET = os.getenv("OSS_BUCKET", "wanzioss")

# 阿里云 AccessKey（必须从环境变量配置，禁止硬编码）
ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "")
ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "")


def _get_bucket():
    """获取 OSS Bucket 客户端"""
    try:
        if not ACCESS_KEY_ID or not ACCESS_KEY_SECRET:
            logger.warning("OSS credentials are not configured; skip OSS upload")
            return None
        import oss2
        auth = oss2.Auth(ACCESS_KEY_ID, ACCESS_KEY_SECRET)
        bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)
        return bucket
    except Exception as e:
        logger.error(f"Failed to init OSS bucket: {e}")
        return None


def upload_image_to_oss(image_data: bytes, scene_index: str) -> Optional[str]:
    """
    将图片二进制数据上传到 OSS
    
    Args:
        image_data: 图片二进制数据
        scene_index: 场景标识，用于生成文件名
        
    Returns:
        OSS URL 或 None
    """
    bucket = _get_bucket()
    if not bucket:
        return None
    
    try:
        # 生成 OSS 文件名
        file_name = f"video_images/scene_{scene_index}.png"
        
        # 上传到 OSS，设置正确的 Content-Type 和 Content-Disposition
        # 使用 inline 让文件可以在线预览，而不是强制下载
        headers = {
            'Content-Type': 'image/png',
            'Content-Disposition': 'inline'
        }
        bucket.put_object(file_name, image_data, headers=headers)
        
        # 生成 OSS URL
        oss_url = f"https://{OSS_BUCKET}.{OSS_ENDPOINT.replace('https://', '')}/{file_name}"
        logger.info(f"Uploaded image to OSS: {oss_url}")
        return oss_url
        
    except Exception as e:
        logger.error(f"Failed to upload image to OSS: {e}")
        return None


def upload_audio_to_oss(audio_url: str) -> Optional[str]:
    """
    从 URL 下载音频并上传到 OSS
    
    Args:
        audio_url: 音频原始 URL
        
    Returns:
        OSS URL 或 None
    """
    bucket = _get_bucket()
    if not bucket:
        return None
    
    try:
        # 下载音频
        response = requests.get(audio_url, timeout=30)
        response.raise_for_status()
        audio_data = response.content
        
        # 生成 OSS 文件名
        import time
        timestamp = int(time.time() * 1000)
        file_name = f"tts_audio/audio_{timestamp}.mp3"
        
        # 上传到 OSS，设置正确的 Content-Type 和 Content-Disposition
        # 使用 inline 让文件可以在线播放，而不是强制下载
        headers = {
            'Content-Type': 'audio/mpeg',
            'Content-Disposition': 'inline'
        }
        bucket.put_object(file_name, audio_data, headers=headers)
        
        # 生成 OSS URL
        oss_url = f"https://{OSS_BUCKET}.{OSS_ENDPOINT.replace('https://', '')}/{file_name}"
        logger.info(f"Uploaded audio to OSS: {oss_url}")
        return oss_url
        
    except Exception as e:
        logger.error(f"Failed to upload audio to OSS: {e}")
        return None
