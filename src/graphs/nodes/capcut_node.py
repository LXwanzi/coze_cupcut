"""
CapCut Mate API 节点
输入: video_plan, audio_url
输出: draft_url
"""
import json
import logging
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)

# CapCut Mate API 基础 URL
CAPCUT_MATE_BASE_URL = "http://your-server-ip:30000/openapi/capcut-mate/v1"


def create_capcut_draft(state: Dict[str, Any]) -> Dict[str, Any]:
    """调用 CapCut Mate API 创建剪映草稿"""
    
    video_plan = state.get("video_plan")
    audio_url = state.get("audio_url")
    
    if not video_plan:
        return {
            "success": False,
            "draft_url": None,
            "error": "缺少 video_plan"
        }
    
    if not audio_url:
        return {
            "success": False,
            "draft_url": None,
            "error": "缺少 audio_url"
        }
    
    canvas = video_plan.get("canvas", {})
    scenes = video_plan.get("scenes", [])
    captions = video_plan.get("captions", [])
    duration = video_plan.get("duration", 0)
    
    draft_url = None
    
    try:
        # Step 1: 创建草稿
        logger.info("Creating CapCut draft...")
        create_response = requests.post(
            f"{CAPCUT_MATE_BASE_URL}/create_draft",
            json={
                "width": canvas.get("width", 1080),
                "height": canvas.get("height", 1920)
            },
            timeout=60
        )
        
        if create_response.status_code != 200:
            return {
                "success": False,
                "draft_url": None,
                "error": f"创建草稿失败: HTTP {create_response.status_code}"
            }
        
        create_data = create_response.json()
        if create_data.get("code") != 0:
            return {
                "success": False,
                "draft_url": None,
                "error": f"创建草稿失败: {create_data.get('message', 'Unknown error')}"
            }
        
        draft_url = create_data.get("data", {}).get("draft_url")
        if not draft_url:
            return {
                "success": False,
                "draft_url": None,
                "error": "创建草稿返回的 draft_url 为空"
            }
        
        logger.info(f"Draft created: {draft_url}")
        
        # Step 2: 添加图片分镜
        logger.info("Adding images to draft...")
        image_infos = []
        for scene in scenes:
            if not scene.get("asset_url"):
                return {
                    "success": False,
                    "draft_url": draft_url,
                    "error": f"Scene 缺少 asset_url: {scene}"
                }
            image_infos.append({
                "image_url": scene["asset_url"],
                "start": scene["start"],
                "end": scene["end"]
            })
        
        add_images_response = requests.post(
            f"{CAPCUT_MATE_BASE_URL}/add_images",
            json={
                "draft_url": draft_url,
                "image_infos": json.dumps(image_infos),
                "scale_x": 1,
                "scale_y": 1,
                "transform_x": 0,
                "transform_y": 0
            },
            timeout=60
        )
        
        if add_images_response.status_code != 200:
            return {
                "success": False,
                "draft_url": draft_url,
                "error": f"添加图片失败: HTTP {add_images_response.status_code}"
            }
        
        add_images_data = add_images_response.json()
        if add_images_data.get("code") != 0:
            return {
                "success": False,
                "draft_url": draft_url,
                "error": f"添加图片失败: {add_images_data.get('message', 'Unknown error')}"
            }
        
        logger.info(f"Added {len(image_infos)} images to draft")
        
        # Step 3: 添加配音
        logger.info("Adding audio to draft...")
        add_audio_response = requests.post(
            f"{CAPCUT_MATE_BASE_URL}/add_audios",
            json={
                "draft_url": draft_url,
                "audio_infos": json.dumps([{
                    "audio_url": audio_url,
                    "start": 0,
                    "end": duration,
                    "volume": 1.0
                }])
            },
            timeout=60
        )
        
        if add_audio_response.status_code != 200:
            return {
                "success": False,
                "draft_url": draft_url,
                "error": f"添加配音失败: HTTP {add_audio_response.status_code}"
            }
        
        add_audio_data = add_audio_response.json()
        if add_audio_data.get("code") != 0:
            return {
                "success": False,
                "draft_url": draft_url,
                "error": f"添加配音失败: {add_audio_data.get('message', 'Unknown error')}"
            }
        
        logger.info("Audio added to draft")
        
        # Step 4: 添加字幕
        logger.info("Adding captions to draft...")
        add_captions_response = requests.post(
            f"{CAPCUT_MATE_BASE_URL}/add_captions",
            json={
                "draft_url": draft_url,
                "captions": json.dumps(captions),
                "text_color": "#ffffff",
                "border_color": "#000000",
                "alignment": 1,
                "font_size": 14,
                "bold": True,
                "has_shadow": True,
                "transform_y": 650
            },
            timeout=60
        )
        
        if add_captions_response.status_code != 200:
            return {
                "success": False,
                "draft_url": draft_url,
                "error": f"添加字幕失败: HTTP {add_captions_response.status_code}"
            }
        
        add_captions_data = add_captions_response.json()
        if add_captions_data.get("code") != 0:
            return {
                "success": False,
                "draft_url": draft_url,
                "error": f"添加字幕失败: {add_captions_data.get('message', 'Unknown error')}"
            }
        
        logger.info(f"Added {len(captions)} captions to draft")
        
        # Step 5: 保存草稿
        logger.info("Saving draft...")
        save_response = requests.post(
            f"{CAPCUT_MATE_BASE_URL}/save_draft",
            json={
                "draft_url": draft_url
            },
            timeout=60
        )
        
        if save_response.status_code != 200:
            return {
                "success": False,
                "draft_url": draft_url,
                "error": f"保存草稿失败: HTTP {save_response.status_code}"
            }
        
        save_data = save_response.json()
        if save_data.get("code") != 0:
            return {
                "success": False,
                "draft_url": draft_url,
                "error": f"保存草稿失败: {save_data.get('message', 'Unknown error')}"
            }
        
        logger.info("Draft saved successfully")
        
        return {
            "success": True,
            "draft_url": draft_url,
            "duration": duration,
            "scene_count": len(scenes),
            "caption_count": len(captions),
            "error": None
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"CapCut API request error: {e}")
        return {
            "success": False,
            "draft_url": draft_url,
            "error": f"CapCut API 请求失败: {str(e)}"
        }
    except Exception as e:
        logger.error(f"CapCut API error: {e}")
        return {
            "success": False,
            "draft_url": draft_url,
            "error": f"CapCut API 异常: {str(e)}"
        }
