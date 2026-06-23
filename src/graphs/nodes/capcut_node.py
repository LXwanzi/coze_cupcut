"""
CapCut Mate API 完整草稿生成流程

API Base URL: http://123.57.144.37:30000/openapi/capcut-mate/v1

流程:
1. POST /create_draft - 创建草稿
2. POST /add_images - 添加图片到草稿
3. POST /add_captions - 添加字幕
4. POST /add_audios - 添加音频（如有）
5. POST /save_draft - 保存草稿

输入: video_plan, audio_url, scenes
输出: final_result (包含 draft_url, steps_status)
"""
import json
import logging
import requests
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# CapCut Mate API 基础 URL
CAPCUT_MATE_BASE_URL = "http://123.57.144.37:30000/openapi/capcut-mate/v1"


def create_capcut_draft(state: Dict[str, Any]) -> Dict[str, Any]:
    """调用 CapCut Mate API 完整流程创建剪映草稿"""

    video_plan = state.get("video_plan")
    audio_url = state.get("audio_url")
    scenes = state.get("scenes")  # 包含 asset_url 的 scenes

    if not video_plan:
        return {
            "success": False,
            "draft_url": None,
            "error": "缺少 video_plan",
            "steps_status": []
        }

    canvas = video_plan.get("canvas", {})
    captions = video_plan.get("captions", [])
    width = canvas.get("width", 1080)
    height = canvas.get("height", 1920)

    # 获取元数据
    content_meta = state.get("content_meta", {})
    publish_pack = state.get("publish_pack", {})
    review_card = state.get("review_card", {})
    material_bank = state.get("material_bank", [])

    draft_url = None
    steps_status: List[Dict] = []

    try:
        # ========== Step 1: 创建草稿 ==========
        logger.info("Step 1: Creating draft...")
        create_payload = {
            "width": width,
            "height": height
        }

        create_response = _safe_post("/create_draft", create_payload)
        steps_status.append({
            "step": "create_draft",
            "url": f"{CAPCUT_MATE_BASE_URL}/create_draft",
            "request": create_payload,
            "response": create_response
        })

        if not create_response or create_response.get("code") != 0:
            return _build_error_result(
                draft_url, content_meta, publish_pack, review_card, material_bank,
                f"创建草稿失败: {create_response}",
                steps_status
            )

        draft_url = create_response.get("draft_url")
        if not draft_url:
            draft_url = create_response.get("data", {}).get("draft_url")
        if not draft_url:
            return _build_error_result(
                draft_url, content_meta, publish_pack, review_card, material_bank,
                "创建草稿返回的 draft_url 为空",
                steps_status
            )

        logger.info(f"Draft created: {draft_url}")

        # ========== Step 2: 添加图片 ==========
        if scenes and len(scenes) > 0:
            image_infos_list = []

            for scene in scenes:
                asset_url = scene.get("asset_url")
                if not asset_url:
                    return _build_error_result(
                        draft_url, content_meta, publish_pack, review_card, material_bank,
                        f"Scene 缺少 asset_url: {scene}",
                        steps_status
                    )
                image_infos_list.append({
                    "image_url": asset_url,
                    "width": width,
                    "height": height,
                    "start": scene.get("start", 0),
                    "end": scene.get("end", 0)
                })

            logger.info(f"Step 2: Adding {len(image_infos_list)} images...")
            add_images_payload = {
                "draft_url": draft_url,
                "image_infos": json.dumps(image_infos_list, ensure_ascii=False),
                "scale_x": 1.0,
                "scale_y": 1.0,
                "transform_x": 0,
                "transform_y": 0
            }

            add_images_response = _safe_post("/add_images", add_images_payload)
            steps_status.append({
                "step": "add_images",
                "url": f"{CAPCUT_MATE_BASE_URL}/add_images",
                "request": add_images_payload,
                "response": add_images_response
            })

            if not add_images_response or add_images_response.get("code") != 0:
                return _build_error_result(
                    draft_url, content_meta, publish_pack, review_card, material_bank,
                    f"添加图片失败: {add_images_response}",
                    steps_status
                )

        # ========== Step 3: 添加字幕 ==========
        if captions and len(captions) > 0:
            captions_list = []
            for caption in captions:
                captions_list.append({
                    "start": caption.get("start", 0),
                    "end": caption.get("end", 0),
                    "text": caption.get("text", ""),
                    "font_size": 24
                })

            logger.info(f"Step 3: Adding {len(captions_list)} captions...")
            add_captions_payload = {
                "draft_url": draft_url,
                "captions": json.dumps(captions_list, ensure_ascii=False),
                "text_color": "#ffffff",
                "border_color": None,
                "alignment": 1,
                "font_size": 24,
                "alpha": 1.0
            }

            add_captions_response = _safe_post("/add_captions", add_captions_payload)
            steps_status.append({
                "step": "add_captions",
                "url": f"{CAPCUT_MATE_BASE_URL}/add_captions",
                "request": add_captions_payload,
                "response": add_captions_response
            })

            if not add_captions_response or add_captions_response.get("code") != 0:
                return _build_error_result(
                    draft_url, content_meta, publish_pack, review_card, material_bank,
                    f"添加字幕失败: {add_captions_response}",
                    steps_status
                )

        # ========== Step 4: 添加音频 ==========
        if audio_url:
            duration = video_plan.get("duration", 60000000)

            logger.info("Step 4: Adding audio...")
            add_audios_payload = {
                "draft_url": draft_url,
                "audio_infos": json.dumps([{
                    "audio_url": audio_url,
                    "start": 0,
                    "end": duration,
                    "volume": 1.0
                }], ensure_ascii=False)
            }

            add_audios_response = _safe_post("/add_audios", add_audios_payload)
            steps_status.append({
                "step": "add_audios",
                "url": f"{CAPCUT_MATE_BASE_URL}/add_audios",
                "request": add_audios_payload,
                "response": add_audios_response
            })

            if not add_audios_response or add_audios_response.get("code") != 0:
                return _build_error_result(
                    draft_url, content_meta, publish_pack, review_card, material_bank,
                    f"添加音频失败: {add_audios_response}",
                    steps_status
                )

        # ========== Step 5: 保存草稿 ==========
        logger.info("Step 5: Saving draft...")
        save_payload = {
            "draft_url": draft_url
        }

        save_response = _safe_post("/save_draft", save_payload)
        steps_status.append({
            "step": "save_draft",
            "url": f"{CAPCUT_MATE_BASE_URL}/save_draft",
            "request": save_payload,
            "response": save_response
        })

        if not save_response or save_response.get("code") != 0:
            return _build_error_result(
                draft_url, content_meta, publish_pack, review_card, material_bank,
                f"保存草稿失败: {save_response}",
                steps_status
            )

        logger.info(f"Draft saved successfully: {draft_url}")

        # ========== 返回成功结果 ==========
        return {
            "success": True,
            "draft_url": draft_url,
            "content_meta": content_meta,
            "publish_pack": publish_pack,
            "review_card": review_card,
            "material_bank": material_bank,
            "steps_status": steps_status,
            "message": "剪映草稿已生成，请用 CapCut Mate 桌面端导入剪映。"
        }

    except Exception as e:
        logger.error(f"CapCut API exception: {str(e)}")
        return _build_error_result(
            draft_url, content_meta, publish_pack, review_card, material_bank,
            f"CapCut API 请求异常: {str(e)}",
            steps_status
        )


def _safe_post(endpoint: str, payload: Dict) -> Dict:
    """安全的 POST 请求"""
    try:
        url = f"{CAPCUT_MATE_BASE_URL}{endpoint}"
        logger.info(f"POST {url}")

        # 记录关键参数（避免过长）
        safe_payload = _truncate_for_logging(payload)
        logger.info(f"Payload: {json.dumps(safe_payload, ensure_ascii=False)[:500]}")

        response = requests.post(url, json=payload, timeout=120)
        result = response.json()

        logger.info(f"Response code: {result.get('code')}, message: {result.get('message')}")
        return result

    except requests.exceptions.ConnectionError as e:
        logger.error(f"连接失败: {str(e)}")
        return {"code": -1, "message": f"连接失败: {str(e)}", "data": None}

    except requests.exceptions.Timeout as e:
        logger.error(f"请求超时: {str(e)}")
        return {"code": -1, "message": f"请求超时: {str(e)}", "data": None}

    except Exception as e:
        logger.error(f"请求异常: {str(e)}")
        return {"code": -1, "message": f"请求异常: {str(e)}", "data": None}


def _truncate_for_logging(payload: Dict) -> Dict:
    """截断过长的 payload 用于日志"""
    safe = {}
    for key, value in payload.items():
        if isinstance(value, str) and len(value) > 200:
            safe[key] = value[:200] + "...(truncated)"
        else:
            safe[key] = value
    return safe


def _build_error_result(
    draft_url: str,
    content_meta: Dict,
    publish_pack: Dict,
    review_card: Dict,
    material_bank: List,
    error_msg: str,
    steps_status: List
) -> Dict:
    """构建错误结果"""
    return {
        "success": False,
        "draft_url": draft_url,
        "content_meta": content_meta,
        "publish_pack": publish_pack,
        "review_card": review_card,
        "material_bank": material_bank,
        "error": error_msg,
        "steps_status": steps_status,
        "message": f"草稿生成失败: {error_msg}"
    }
