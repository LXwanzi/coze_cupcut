"""
OSS 存储辅助模块
提供图片和音频上传到阿里云 OSS 的功能
"""
import logging
import hashlib
from typing import Optional

logger = logging.getLogger(__name__)

# OSS 配置
OSS_ENDPOINT = "https://oss-cn-beijing.aliyuncs.com"
OSS_BUCKET = "coze-video-assets"
OSS_REGION = "cn-beijing"

# 阿里云 AccessKey（请根据实际情况配置）
ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "")
ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "")


def _get_storage():
    """获取 OSS 存储客户端"""
    try:
        from coze_coding_dev_sdk.s3 import S3SyncStorage
        storage = S3SyncStorage(
            endpoint_url=OSS_ENDPOINT,
            access_key=ACCESS_KEY_ID,
            secret_key=ACCESS_KEY_SECRET,
            bucket_name=OSS_BUCKET,
            region=OSS_REGION,
        )
        return storage
    except Exception as e:
        logger.error(f"Failed to init OSS storage: {e}")
        return None


def upload_image_to_oss(image_url: str, scene_index: int) -> Optional[str]:
    """
    从 URL 下载图片并上传到 OSS
    返回 OSS 公网 URL（带签名）
    """
    try:
        storage = _get_storage()
        if not storage:
            return None

        # 使用 upload_from_url 直接从远程 URL 转存
        key = storage.upload_from_url(url=image_url, timeout=60)
        if not key:
            logger.error(f"Failed to upload image from {image_url}")
            return None

        # 生成带签名的公网 URL（有效期 7 天）
        oss_url = storage.generate_presigned_url(key=key, expire_time=7 * 24 * 3600)
        logger.info(f"Image uploaded to OSS: {oss_url[:80]}...")
        return oss_url

    except Exception as e:
        logger.error(f"Upload image to OSS failed: {e}")
        return None


def upload_audio_to_oss(audio_url: str) -> Optional[str]:
    """
    从 URL 下载音频并上传到 OSS
    返回 OSS 公网 URL（带签名）
    """
    try:
        storage = _get_storage()
        if not storage:
            return None

        # 使用 upload_from_url 直接从远程 URL 转存
        key = storage.upload_from_url(url=audio_url, timeout=60)
        if not key:
            logger.error(f"Failed to upload audio from {audio_url}")
            return None

        # 生成带签名的公网 URL（有效期 7 天）
        oss_url = storage.generate_presigned_url(key=key, expire_time=7 * 24 * 3600)
        logger.info(f"Audio uploaded to OSS: {oss_url[:80]}...")
        return oss_url

    except Exception as e:
        logger.error(f"Upload audio to OSS failed: {e}")
        return None
