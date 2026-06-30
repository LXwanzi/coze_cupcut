"""
CapCut Mate API 完整草稿生成流程 - 音频同步版 + 动画效果

API Base URL: http://123.57.144.37:30000/openapi/capcut-mate/v1

流程:
1. POST /create_draft - 创建草稿
2. POST /imgs_infos - 生成带入场动画的图片信息
3. POST /add_images - 添加图片到草稿（基于音频时间轴）
4. POST /caption_infos - 生成带入场动画的字幕信息
5. POST /add_captions - 添加字幕（深色文字+白色背景+顶部位置）
6. POST /add_audios - 添加音频（片段级同步）
7. POST /keyframes_infos - 生成关键帧信息（Ken Burns 画面推进效果）
8. POST /add_keyframes - 添加关键帧到草稿
9. POST /save_draft - 保存草稿

核心原则:
- 所有片段（图片、字幕、音频）必须使用相同的 start/end 时间轴
- 总时长以音频总时长为准
- 字幕固定在顶部安全区
- 支持添加 BGM 背景音乐
- 图片添加入场动画（向上滑动）
- 字幕添加入场动画（向上滑动）
- 图片添加 Ken Burns 关键帧动画（缓慢推进）
"""
import json
import logging
import os
import requests
from typing import Dict, Any, List, Optional

from graphs.nodes.output_writer import write_workflow_output

logger = logging.getLogger(__name__)

# ========== BGM 配置 ==========
# 设置 BGM URL 即可添加背景音乐
# 可选 BGM 风格：
# - "none" 或空: 不添加 BGM
# - 自定义 URL: 使用你自己的 BGM 音频 URL

BGM_URL = os.getenv("BGM_URL", "")  # 环境变量配置
BGM_VOLUME = 0.3  # BGM 音量 (0.0-1.0)，配音为主，BGM 作为背景

# 内置 BGM 示例（需要替换为实际可用的 URL）
# BGM_URL = "https://your-oss-bucket/bgm/light_piano.mp3"
# =================================

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
            "keywords": source_seg.get("keywords", []),
            "caption_highlight": source_seg.get("caption_highlight", {}),
            "animation": source_seg.get("animation", {}),
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
        result = {
            "success": False,
            "draft_url": None,
            "error": "缺少 video_plan",
            "steps_status": []
        }
        return _finalize_result(state, result)

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
            return _finalize_result(state, _build_error_result(
                draft_url, content_meta, publish_pack, review_card, material_bank,
                timeline_error,
                steps_status
            ))

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
            return _finalize_result(state, _build_error_result(
                draft_url, content_meta, publish_pack, review_card, material_bank,
                f"创建草稿失败: {create_response}",
                steps_status
            ))

        draft_url = create_response.get("draft_url")
        if not draft_url:
            draft_url = create_response.get("data", {}).get("draft_url")
        if not draft_url:
            return _finalize_result(state, _build_error_result(
                draft_url, content_meta, publish_pack, review_card, material_bank,
                "创建草稿返回的 draft_url 为空",
                steps_status
            ))

        logger.info(f"Draft created: {draft_url}")

        # ========== Step 2: 添加图片（带入场动画）==========
        # 构建图片时间线列表
        image_urls = []
        image_timelines = []
        for seg in timeline_segments:
            image_urls.append(seg["asset_url"])
            image_timelines.append({
                "start": seg["start"],
                "end": seg["end"]
            })

        if image_urls:
            logger.info(f"Step 2: Adding {len(image_urls)} images with in-animation...")

            # Step 2a: 调用 imgs_infos 生成带入场动画的图片信息
            imgs_infos_payload = {
                "imgs": image_urls,
                "timelines": image_timelines,
                "width": width,
                "height": height,
                "in_animation": "向上滑动",
                "in_animation_duration": 500000  # 0.5秒入场动画
            }

            imgs_infos_response = _safe_post("/imgs_infos", imgs_infos_payload)
            steps_status.append({
                "step": "imgs_infos",
                "url": f"{CAPCUT_MATE_BASE_URL}/imgs_infos",
                "request": {k: v for k, v in imgs_infos_payload.items() if k != "imgs"},
                "response": {"code": imgs_infos_response.get("code"), "message": imgs_infos_response.get("message")} if imgs_infos_response else None
            })

            if not imgs_infos_response or imgs_infos_response.get("code") != 0:
                logger.warning(f"imgs_infos failed, falling back to basic image_infos: {imgs_infos_response}")
                # 降级：不使用动画，直接构建 image_infos
                image_infos_list = [
                    {"image_url": url, "width": width, "height": height,
                     "start": tl["start"], "end": tl["end"]}
                    for url, tl in zip(image_urls, image_timelines)
                ]
            else:
                # 使用带动画的图片信息
                image_infos_str = imgs_infos_response.get("infos", "[]")
                image_infos_list = json.loads(image_infos_str) if isinstance(image_infos_str, str) else image_infos_str

            # Step 2b: 调用 add_images 将图片添加到草稿
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
                "request": {k: v for k, v in add_images_payload.items() if k != "image_infos"},
                "response": add_images_response
            })

            if not add_images_response or add_images_response.get("code") != 0:
                return _finalize_result(state, _build_error_result(
                    draft_url, content_meta, publish_pack, review_card, material_bank,
                    f"添加图片失败: {add_images_response}",
                    steps_status
                ))

        # ========== Step 2.5: 添加关键帧动画（Ken Burns 画面推进效果）==========
        # 为每张图片添加缓慢缩放推进的关键帧动画
        if image_urls:
            logger.info("Step 2.5: Adding Ken Burns keyframe animation...")

            # 构建 segment_infos（每个图片片段的时间信息）
            segment_infos = []
            for i, seg in enumerate(timeline_segments):
                segment_infos.append({
                    "id": str(i),
                    "start": seg["start"],
                    "end": seg["end"]
                })

            # Step 2.5a: 生成 UNIFORM_SCALE 关键帧（从 1.0 缓慢放大到 1.08）
            keyframes_infos_payload = {
                "ctype": "UNIFORM_SCALE",
                "offsets": "0|100",  # 在片段的开始和结尾放置关键帧
                "values": "1.0|1.08",  # 从 100% 缩放到 108%
                "segment_infos": segment_infos,
                "width": width,
                "height": height
            }

            keyframes_infos_response = _safe_post("/keyframes_infos", keyframes_infos_payload)
            steps_status.append({
                "step": "keyframes_infos",
                "url": f"{CAPCUT_MATE_BASE_URL}/keyframes_infos",
                "request": {k: v for k, v in keyframes_infos_payload.items() if k != "segment_infos"},
                "response": {"code": keyframes_infos_response.get("code"), "message": keyframes_infos_response.get("message")} if keyframes_infos_response else None
            })

            if keyframes_infos_response and keyframes_infos_response.get("code") == 0:
                keyframes_str = keyframes_infos_response.get("keyframes_infos", "[]")

                # Step 2.5b: 将关键帧应用到草稿
                add_keyframes_payload = {
                    "draft_url": draft_url,
                    "keyframes": keyframes_str
                }

                add_keyframes_response = _safe_post("/add_keyframes", add_keyframes_payload)
                steps_status.append({
                    "step": "add_keyframes",
                    "url": f"{CAPCUT_MATE_BASE_URL}/add_keyframes",
                    "request": {"draft_url": draft_url, "keyframes_length": len(keyframes_str)},
                    "response": add_keyframes_response
                })

                if add_keyframes_response and add_keyframes_response.get("code") == 0:
                    logger.info("Ken Burns keyframe animation added successfully")
                else:
                    logger.warning(f"add_keyframes failed (non-critical): {add_keyframes_response}")
            else:
                logger.warning(f"keyframes_infos failed (non-critical): {keyframes_infos_response}")

        # ========== Step 3: 添加字幕（带入场动画）==========
        # 构建字幕列表 - 基于片段时间轴，使用深色文字+白色背景+底部位置
        caption_texts = []
        caption_timelines = []
        for seg in timeline_segments:
            caption_texts.append(seg["caption"])
            caption_timelines.append({
                "start": seg["start"],
                "end": seg["end"]
            })

        if caption_texts:
            logger.info(f"Step 3: Adding {len(caption_texts)} captions with in-animation...")

            # Step 3a: 调用 caption_infos 生成带入场动画的字幕信息
            caption_infos_payload = {
                "texts": caption_texts,
                "timelines": caption_timelines,
                "in_animation": "向上滑动",
                "in_animation_duration": 500000  # 0.5秒入场动画
            }

            caption_infos_response = _safe_post("/caption_infos", caption_infos_payload)
            steps_status.append({
                "step": "caption_infos",
                "url": f"{CAPCUT_MATE_BASE_URL}/caption_infos",
                "request": {k: v for k, v in caption_infos_payload.items() if k != "texts"},
                "response": {"code": caption_infos_response.get("code"), "message": caption_infos_response.get("message")} if caption_infos_response else None
            })

            if not caption_infos_response or caption_infos_response.get("code") != 0:
                logger.warning(f"caption_infos failed, falling back to basic captions: {caption_infos_response}")
                # 降级：不使用动画，直接构建 captions
                captions_list = [
                    {"start": tl["start"], "end": tl["end"], "text": txt, "font_size": 10}
                    for txt, tl in zip(caption_texts, caption_timelines)
                ]
            else:
                # 使用带动画的字幕信息
                captions_str = caption_infos_response.get("infos", "[]")
                captions_list = json.loads(captions_str) if isinstance(captions_str, str) else captions_str

            # Step 3b: 调用 add_captions 将字幕添加到草稿
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
                # 字号10
                "font_size": 10,
                # 透明度
                "alpha": 1.0,
                "bold": True,
                "italic": True,  # 斜体
                "line_spacing": 2,
                # 阴影增加可读性
                "has_shadow": True,
                "shadow_info": {
                    "shadow_color": "#000000",
                    "shadow_alpha": 0.3,
                    "shadow_diffuse": 4,
                    "shadow_distance": 2,
                    "shadow_angle": -45
                },
                # 字幕位置Y轴
                "transform_x": 0,
                "transform_y": 630
            }

            add_captions_response = _safe_post("/add_captions", add_captions_payload)
            steps_status.append({
                "step": "add_captions",
                "url": f"{CAPCUT_MATE_BASE_URL}/add_captions",
                "request": {k: v for k, v in add_captions_payload.items() if k != "captions"},
                "response": add_captions_response
            })

            if not add_captions_response or add_captions_response.get("code") != 0:
                return _finalize_result(state, _build_error_result(
                    draft_url, content_meta, publish_pack, review_card, material_bank,
                    f"添加字幕失败: {add_captions_response}",
                    steps_status
                ))

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
                return _finalize_result(state, _build_error_result(
                    draft_url, content_meta, publish_pack, review_card, material_bank,
                    f"添加音频失败: {add_audios_response}",
                    steps_status
                ))

        # ========== Step 4.5: 添加 BGM（可选）==========
        # 检查是否有 BGM 配置
        bgm_url = state.get("bgm_url") or BGM_URL
        if bgm_url and bgm_url.lower() not in ["none", "", "false"]:
            logger.info(f"Step 4.5: Adding BGM from {bgm_url}...")
            # BGM 从 0 开始，贯穿整个视频
            bgm_infos_list = [{
                "audio_url": bgm_url,
                "start": 0,
                "end": total_audio_duration,
                "duration": total_audio_duration,
                "volume": BGM_VOLUME  # BGM 音量较低，作为背景
            }]
            
            add_bgm_payload = {
                "draft_url": draft_url,
                "audio_infos": json.dumps(bgm_infos_list, ensure_ascii=False)
            }
            
            add_bgm_response = _safe_post("/add_audios", add_bgm_payload)
            steps_status.append({
                "step": "add_bgm",
                "url": f"{CAPCUT_MATE_BASE_URL}/add_audios",
                "request": add_bgm_payload,
                "response": add_bgm_response
            })
            
            if add_bgm_response and add_bgm_response.get("code") == 0:
                logger.info("BGM added successfully")
            else:
                logger.warning(f"BGM add failed (non-critical): {add_bgm_response}")

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
            return _finalize_result(state, _build_error_result(
                draft_url, content_meta, publish_pack, review_card, material_bank,
                f"保存草稿失败: {save_response}",
                steps_status
            ))

        # 替换 draft_url 域名为用户配置的地址
        final_draft_url = draft_url.replace(
            "https://capcut-mate.jcaigc.cn",
            "http://123.57.144.37:30000"
        )

        logger.info(f"Draft saved successfully: {draft_url}")
        logger.info(f"Final draft URL (replaced): {final_draft_url}")

        # ========== 返回成功结果 ==========
        success_result = {
            "success": True,
            "draft_url": final_draft_url,
            "content_meta": content_meta,
            "publish_pack": publish_pack,
            "review_card": review_card,
            "material_bank": material_bank,
            "segments": state.get("segments", []),
            "duration": total_audio_duration,
            "duration_seconds": round(total_audio_duration / MICROSECONDS_PER_SECOND, 2),
            "scene_count": len(timeline_segments),
            "caption_count": len(timeline_segments),
            "timeline_segments": timeline_segments,
            "steps_status": steps_status,
            "message": "剪映草稿已生成，请用 CapCut Mate 桌面端导入剪映。"
        }
        return _finalize_result(state, success_result)

    except Exception as e:
        logger.error(f"CapCut API exception: {str(e)}")
        error_result = _build_error_result(
            draft_url, content_meta, publish_pack, review_card, material_bank,
            f"CapCut API 请求异常: {str(e)}",
            steps_status
        )
        return _finalize_result(state, error_result)


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


def _finalize_result(state: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Attach common output fields and persist the workflow result."""
    result.setdefault("segments", state.get("segments", []))
    result.setdefault("timeline_segments", [])
    result.update(write_workflow_output(state, result))
    return result


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
