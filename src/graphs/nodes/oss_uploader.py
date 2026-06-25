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


def upload_image_to_oss(image_url: str, scene_index: int) -> Optional[str]:
    """
    从 URL 下载图片并上传到 OSS
    
    Args:
        image_url: 图片原始 URL
        scene_index: 片段索引，用于生成文件名
        
    Returns:
        OSS URL 或 None
    """
    bucket = _get_bucket()
    if not bucket:
        return None
    
    try:
        # 下载图片
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        image_data = response.content
        
        # 生成 OSS 文件名
        file_name = f"video_images/scene_{scene_index}.png"
        
        # 上传到 OSS
        bucket.put_object(file_name, image_data)
        
        # 生成 OSS URL
        oss_url = f"https://{OSS_BUCKET}.{OSS_ENDPOINT.replace('https://', '')}/{file_name}"
        logger.info(f"Uploaded image to OSS: {oss_url}")
        return oss_url
        
    except Exception as e:
        logger.error(f"Failed to upload image to OSS: {e}")
        return None
