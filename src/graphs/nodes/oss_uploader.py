"""
OSS 存储辅助模块
提供图片和音频上传到阿里云 OSS 的功能
"""
import logging
import tempfile
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# OSS 配置
OSS_ENDPOINT = "https://oss-cn-beijing.aliyuncs.com"
OSS_BUCKET = "coze-video-assets"

# 阿里云 AccessKey
ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "")
ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "")


def _get_bucket():
    """获取 OSS Bucket 客户端"""
    try:
        import oss2
        auth = oss2.Auth(ACCESS_KEY_ID, ACCESS_KEY_SECRET)
        bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)
        return bucket
    except Exception as e:
        logger.error(f"Failed to init OSS bucket: {e}")
        return None


def upload_image_to_oss(image_url: str, scene_index: int) -> Optional[str]:
    """
    从 URL 下载图片并上传到 OSS
    返回 OSS 公网 URL（公共读取，无需签名）
    """
    try:
        bucket = _get_bucket()
        if not bucket:
            return None

        # 下载图片到临时文件
        response = requests.get(image_url, timeout=30)
        if response.status_code != 200:
            logger.error(f"Failed to download image: {response.status_code}")
            return None

        # 上传到 OSS
        object_key = f"images/scene_{scene_index}_{hash_url(image_url)}.jpg"
        result = bucket.put_object(object_key, response.content)
        
        if result.status == 200:
            # 生成公共读取 URL（不带签名）
            oss_url = f"https://{OSS_BUCKET}.{OSS_ENDPOINT.replace('https://', '')}/{object_key}"
            logger.info(f"Image uploaded to OSS: {oss_url}")
            return oss_url
        else:
            logger.error(f"Failed to upload image, status: {result.status}")
            return None

    except Exception as e:
        logger.error(f"Upload image to OSS failed: {e}")
        return None


def upload_audio_to_oss(audio_url: str) -> Optional[str]:
    """
    从 URL 下载音频并上传到 OSS
    返回 OSS 公网 URL（公共读取，无需签名）
    """
    try:
        bucket = _get_bucket()
        if not bucket:
            return None

        # 下载音频到临时文件
        response = requests.get(audio_url, timeout=60)
        if response.status_code != 200:
            logger.error(f"Failed to download audio: {response.status_code}")
            return None

        # 上传到 OSS
        object_key = f"audio/voice_{hash_url(audio_url)}.mp3"
        result = bucket.put_object(object_key, response.content)
        
        if result.status == 200:
            # 生成公共读取 URL（不带签名）
            oss_url = f"https://{OSS_BUCKET}.{OSS_ENDPOINT.replace('https://', '')}/{object_key}"
            logger.info(f"Audio uploaded to OSS: {oss_url}")
            return oss_url
        else:
            logger.error(f"Failed to upload audio, status: {result.status}")
            return None

    except Exception as e:
        logger.error(f"Upload audio to OSS failed: {e}")
        return None


def hash_url(url: str) -> str:
    """生成短哈希用于文件命名"""
    import hashlib
    return hashlib.md5(url.encode()).hexdigest()[:12]
