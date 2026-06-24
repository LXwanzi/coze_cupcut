"""
CapCut Mate API 完整草稿生成流程 - 音频同步版

API Base URL: http://123.57.144.37:30000/openapi/capcut-mate/v1

流程:
1. POST /create_draft - 创建草稿
2. POST /add_images - 添加图片到草稿（基于音频时间轴）
3. POST /add_captions - 添加字幕（深色文字+白色背景+底部位置）
4. POST /add_audios - 添加音频（片段级同步）
5. POST /save_draft - 保存草稿

核心原则:
- 所有片段（图片、字幕、音频）必须使用相同的 start/end 时间轴
- 总时长以音频总时长为准
- 字幕固定在底部安全区
"""
import json
import logging
import os
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# CapCut Mate API 基础 URL
CAPCUT_MATE_BASE_URL = os.getenv(
    "CAPCUT_MATE_BASE_URL",
    "http://123.57.144.37:30000/openapi/capcut-mate/v1"
)
MICROSECONDS_PER_SECOND = 1_000_000


def _to_microseconds(value: Any) -> int:
    """Normalize seconds/microseconds-like values to integer microseconds."""
    if value is None:
        return 0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    # TTS 节点旧版本可能传秒；新版本传微秒。小于 10_000 基本可判定为秒。
    if 0 < number < 10_000:
        number *= MICROSECONDS_PER_SECOND
    return int(round(number))


def _build_timeline_segments(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build one authoritative timeline used by images, captions, and audio."""
    audio_segments = state.get("audio_segments") or []
    segments = state.get("segments") or []
    scenes = state.get("scenes") or []
    timeline_segments: List[Dict[str, Any]] = []
    current_start = 0

    for i, audio_seg in enumerate(audio_segments):
        source_seg = audio_seg.get("scene_data") or (segments[i] if i < len(segments) else {})
        scene = scenes[i] if i < len(scenes) else {}
        start = _to_microseconds(audio_seg.get("start"))
        if start <= 0 and i > 0:
            start = current_start

        duration = _to_microseconds(audio_seg.get("duration"))
        end = _to_microseconds(audio_seg.get("end"))
        if end <= start:
            end = start + max(duration, 1_500_000)

        asset_url = (
            audio_seg.get("asset_url")
            or audio_seg.get("image_url")
            or source_seg.get("asset_url")
            or source_seg.get("image_url")
            or scene.get("asset_url")
        )

        timeline_segments.append({
            "index": audio_seg.get("index", i),
            "start": start,
            "end": end,
            "duration": end - start,
            "caption": audio_seg.get("caption") or source_seg.get("caption", ""),
            "audio_url": audio_seg.get("audio_url") or audio_seg.get("url"),
            "asset_url": asset_url,
            "scene": audio_seg.get("scene") or source_seg.get("scene", ""),
        })
        current_start = end

    return timeline_segments


def _validate_timeline(timeline_segments: List[Dict[str, Any]]) -> Optional[str]:
    if not timeline_segments:
        return "没有可用的片段级时间轴"
    for i, seg in enumerate(timeline_segments):
        if not seg.get("audio_url"):
            return f"片段 {i} 缺少 audio_url"
        if not seg.get("asset_url"):
            return f"片段 {i} 缺少图片 asset_url"
        if not seg.get("caption"):
            return f"片段 {i} 缺少字幕 caption"
        if int(seg.get("end", 0)) <= int(seg.get("start", 0)):
            return f"片段 {i} 时间范围无效: {seg.get('start')} - {seg.get('end')}"
    return None


def create_capcut_draft(state: Dict[str, Any]) -> Dict[str, Any]:
    """调用 CapCut Mate API 完整流程创建剪映草稿

    核心同步逻辑:
    - audio_segments 包含每个片段的 start/end 时间轴
    - 每个片段包含: scene, caption, audio_url, duration, start, end
    - 图片和字幕使用相同的时间轴
    - 总时长以最后一个音频片段的 end 为准
    """

    video_plan = state.get("video_plan")
    audio_segments = state.get("audio_segments", [])  # 片段级音频（已包含时间轴）
    audio_url = state.get("audio_url")  # 备用：整段音频
    scenes = state.get("scenes", [])  # 包含 asset_url 的 scenes

    if not video_plan:
        return {
            "success": False,
            "draft_url": None,
            "error": "缺少 video_plan",
            "steps_status": []
        }

    canvas = video_plan.get("canvas", {})
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
        # ========== 校验时间轴 ==========
        # 只使用一套权威时间轴，后续图片、字幕、音频都从这里派生。
        timeline_segments = _build_timeline_segments(state)
        timeline_error = _validate_timeline(timeline_segments)
        if timeline_error:
            return _build_error_result(
                draft_url, content_meta, publish_pack, review_card, material_bank,
                timeline_error,
                steps_status
            )

        total_audio_duration = max(seg["end"] for seg in timeline_segments)

        logger.info(f"Total audio duration: {total_audio_duration} μs ({total_audio_duration / 1000000:.2f}s)")
        logger.info(f"Timeline segments count: {len(timeline_segments)}")

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
        # 构建图片信息列表 - 使用片段时间轴
        image_infos_list = []
        for seg in timeline_segments:
            image_infos_list.append({
                "image_url": seg["asset_url"],
                "width": width,
                "height": height,
                "start": seg["start"],
                "end": seg["end"]
            })

        if image_infos_list:
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
        # 构建字幕列表 - 基于片段时间轴，使用深色文字+白色背景+底部位置
        captions_list = []
        for seg in timeline_segments:
            captions_list.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["caption"],
                "font_size": 42
            })

        if captions_list:
            logger.info(f"Step 3: Adding {len(captions_list)} captions with bottom position...")
            add_captions_payload = {
                "draft_url": draft_url,
                "captions": json.dumps(captions_list, ensure_ascii=False),
                # 深色文字在浅色背景上更清晰
                "text_color": "#111111",
                # 白色半透明背景（通过描边模拟）
                "border_color": "#FFFFFF",
                "border_width": 2,
                # 居中对齐
                "alignment": 1,
                # 较大字号，移动端可读
                "font_size": 42,
                # 透明度
                "alpha": 1.0,
                "bold": True,
                "line_spacing": 4,
                # 阴影增加可读性
                "has_shadow": True,
                "shadow_info": {
                    "shadow_color": "#000000",
                    "shadow_alpha": 0.35,
                    "shadow_diffuse": 8,
                    "shadow_distance": 4,
                    "shadow_angle": -45
                },
                # 底部安全区位置 (画布高度 1920，字幕放底部约 2/3 处)
                "transform_x": 0,
                "transform_y": 620
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
        # 使用片段级音频同步
        audio_infos_list = []
        for seg in timeline_segments:
            audio_infos_list.append({
                "audio_url": seg["audio_url"],
                "start": seg["start"],
                "end": seg["end"],
                "duration": seg["duration"],
                "volume": 1.0
            })

        if audio_infos_list:
            logger.info(f"Step 4: Adding {len(audio_infos_list)} audio segments...")
            add_audios_payload = {
                "draft_url": draft_url,
                "audio_infos": json.dumps(audio_infos_list, ensure_ascii=False)
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

        # 替换 draft_url 域名为用户配置的地址
        final_draft_url = draft_url.replace(
            "https://capcut-mate.jcaigc.cn",
            "http://123.57.144.37:30000"
        )

        logger.info(f"Draft saved successfully: {draft_url}")
        logger.info(f"Final draft URL (replaced): {final_draft_url}")

        # ========== 返回成功结果 ==========
        return {
            "success": True,
            "draft_url": final_draft_url,
            "content_meta": content_meta,
            "publish_pack": publish_pack,
            "review_card": review_card,
            "material_bank": material_bank,
            "duration": total_audio_duration,
            "duration_seconds": round(total_audio_duration / MICROSECONDS_PER_SECOND, 2),
            "scene_count": len(timeline_segments),
            "caption_count": len(timeline_segments),
            "timeline_segments": timeline_segments,
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
