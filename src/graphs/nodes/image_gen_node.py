"""Account-aware AI image generation node.

Input: video_plan / segments.
Output: scenes, each with asset_url.

Visual style, reference image, fixed images, forbidden terms, and subtitle safe
areas are read from accounts/<account_id>/visual.json.
"""
import logging
import requests
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from coze_coding_dev_sdk import ImageGenerationClient
from coze_coding_utils.runtime_ctx.context import new_context
from content.account_loader import get_account_pack
from graphs.nodes.oss_uploader import upload_image_to_oss

logger = logging.getLogger(__name__)
ACCOUNT_PACK = get_account_pack()
VISUAL_CONFIG = ACCOUNT_PACK.get("visual", {})

CHARACTER_REFERENCE_IMAGE_URL = VISUAL_CONFIG.get("reference_image_url", "")
FIXED_IMAGES = VISUAL_CONFIG.get("fixed_images", {})
FIXED_HOOK_IMAGE_URL = FIXED_IMAGES.get("FIXED_HOOK_IMAGE", "")
FIXED_REVIEW_WITH_CHAR_URL = FIXED_IMAGES.get("FIXED_REVIEW_WITH_CHAR", "")

# 缓存已生成的固定图片（仅用于缓存从 URL 下载后的本地路径）
FIXED_HOOK_IMAGE_GENERATED = None
FIXED_REVIEW_BACKGROUND_GENERATED = None

STYLE_SUFFIX = VISUAL_CONFIG.get("style_suffix", "")
POSITION_CONSTRAINTS = VISUAL_CONFIG.get("position_constraints", {})
FORBIDDEN_STYLES = VISUAL_CONFIG.get("forbidden_styles", [])


def _handle_fixed_image(prompt_marker: str, i: int, scene: Dict[str, Any], client: Any) -> tuple:
    """处理固定图片类型：直接使用预置固定 URL，不调用 API"""
    global FIXED_HOOK_IMAGE_GENERATED, FIXED_REVIEW_BACKGROUND_GENERATED

    try:
        if prompt_marker == "FIXED_HOOK_IMAGE":
            fixed_url = _fixed_image_url(prompt_marker)
            if not fixed_url:
                return i, None, f"Scene {i} 缺少固定图片配置: {prompt_marker}"
            cache = FIXED_HOOK_IMAGE_GENERATED

            if cache:
                oss_url = upload_image_to_oss(cache, f"hook_img_{i}")
                asset_url = oss_url if oss_url else cache
            else:
                import requests as req
                resp = req.get(fixed_url, timeout=30)
                if resp.status_code == 200:
                    cache = resp.content
                    FIXED_HOOK_IMAGE_GENERATED = cache
                    oss_url = upload_image_to_oss(cache, f"hook_img_{i}")
                    asset_url = oss_url if oss_url else fixed_url
                else:
                    asset_url = fixed_url

            updated_scene = {
                "start": scene.get("start", 0),
                "end": scene.get("end", 0),
                "type": "image",
                "visual_role": scene.get("visual_role", ""),
                "prompt": prompt_marker,
                "asset_url": asset_url,
                "coze_url": fixed_url
            }
            logger.info(f"Scene {i} FIXED_HOOK_IMAGE (no API call)")
            return i, updated_scene, None

        elif prompt_marker == "FIXED_REVIEW_WITH_CHAR":
            fixed_url = _fixed_image_url(prompt_marker)
            if not fixed_url:
                return i, None, f"Scene {i} 缺少固定图片配置: {prompt_marker}"
            cache = FIXED_REVIEW_BACKGROUND_GENERATED

            if cache:
                oss_url = upload_image_to_oss(cache, f"review_bg_{i}")
                asset_url = oss_url if oss_url else cache
            else:
                import requests as req
                resp = req.get(fixed_url, timeout=30)
                if resp.status_code == 200:
                    cache = resp.content
                    FIXED_REVIEW_BACKGROUND_GENERATED = cache
                    oss_url = upload_image_to_oss(cache, f"review_bg_{i}")
                    asset_url = oss_url if oss_url else fixed_url
                else:
                    asset_url = fixed_url

            updated_scene = {
                "start": scene.get("start", 0),
                "end": scene.get("end", 0),
                "type": "image",
                "visual_role": scene.get("visual_role", ""),
                "prompt": prompt_marker,
                "asset_url": asset_url,
                "coze_url": fixed_url
            }
            logger.info(f"Scene {i} FIXED_REVIEW_WITH_CHAR (no API call)")
            return i, updated_scene, None

        elif prompt_marker == "FIXED_REVIEW_BACKGROUND":
            import requests as req
            fixed_url = _fixed_image_url(prompt_marker)
            if not fixed_url:
                return i, None, f"Scene {i} 缺少固定图片配置: {prompt_marker}"
            cache = FIXED_REVIEW_BACKGROUND_GENERATED

            if cache:
                oss_url = upload_image_to_oss(cache, f"review_bg_plain_{i}")
                asset_url = oss_url if oss_url else cache
            else:
                resp = req.get(fixed_url, timeout=30)
                if resp.status_code == 200:
                    cache = resp.content
                    FIXED_REVIEW_BACKGROUND_GENERATED = cache
                    oss_url = upload_image_to_oss(cache, f"review_bg_plain_{i}")
                    asset_url = oss_url if oss_url else fixed_url
                else:
                    asset_url = None

            if asset_url:
                updated_scene = {
                    "start": scene.get("start", 0),
                    "end": scene.get("end", 0),
                    "type": "image",
                    "visual_role": scene.get("visual_role", ""),
                    "prompt": prompt_marker,
                    "asset_url": asset_url,
                    "coze_url": fixed_url
                }
                logger.info(f"Scene {i} FIXED_REVIEW_BACKGROUND fallback success")
                return i, updated_scene, None
            else:
                return i, None, f"Scene {i} 固定复习背景获取失败"

    except Exception as e:
        logger.error(f"Scene {i} fixed image error: {e}")
        return i, None, f"Scene {i} 固定图片生成异常: {str(e)}"


def _apply_style(prompt: str, scene_type: str = "", use_reference: bool = True) -> str:
    """为 prompt 添加统一风格，并移除禁止的风格关键词
    
    Args:
        prompt: 原始 prompt
        scene_type: 场景类型，用于确定位置约束
        use_reference: 是否追加角色一致性描述
    """
    # 移除禁止的关键词
    clean_prompt = _sanitize_visual_prompt(prompt)
    for forbidden in FORBIDDEN_STYLES:
        clean_prompt = clean_prompt.replace(forbidden, "")

    # 根据场景类型添加位置约束
    if "复习" in scene_type:
        # 复习页：人物缩小放角落，字幕区域留白
        position_constraint = POSITION_CONSTRAINTS.get(
            "review",
            ", IMPORTANT: leave clean empty space for external subtitle overlay"
        )
    elif "标题页" in scene_type:
        position_constraint = POSITION_CONSTRAINTS.get(
            "title",
            ", IMPORTANT: top 25% of the frame is clean and empty for external subtitles"
        )
    else:
        position_constraint = POSITION_CONSTRAINTS.get(
            "default",
            ", IMPORTANT: top 25% of the frame is clean and empty for external subtitles"
        )

    styled_prompt = clean_prompt + STYLE_SUFFIX + position_constraint
    styled_prompt = _append_visual_guard(styled_prompt)
    
    return styled_prompt


def _sanitize_visual_prompt(prompt: str) -> str:
    """Remove account-configured prompt terms that invite in-image text."""
    clean_prompt = prompt or ""
    guard = VISUAL_CONFIG.get("image_prompt_guard", {})
    for forbidden in guard.get("forbidden_prompt_terms", []):
        clean_prompt = clean_prompt.replace(forbidden, "")
    return clean_prompt


def _append_visual_guard(prompt: str) -> str:
    """Append account-level no-text/no-bubble constraints to image prompts."""
    guard = VISUAL_CONFIG.get("image_prompt_guard", {})
    if not guard.get("enabled", True):
        return prompt
    suffixes = guard.get("suffixes", [])
    if not suffixes:
        return prompt
    return f"{prompt}, " + " ".join(suffixes)


def _fixed_image_url(prompt_marker: str) -> str:
    return (FIXED_IMAGES or {}).get(prompt_marker, "")


def _fallback_image_url() -> str:
    return (
        _fixed_image_url("FIXED_HOOK_IMAGE")
        or _fixed_image_url("FIXED_REVIEW_WITH_CHAR")
        or ""
    )


def generate_images(state: Dict[str, Any]) -> Dict[str, Any]:
    """为所有 scenes 生成 AI 图片"""
    ctx = new_context(method="generate_images")
    client = ImageGenerationClient(ctx=ctx)

    # 优先使用 video_plan，如果不存在则从 segments 构建
    video_plan = state.get("video_plan")
    segments = state.get("segments", [])
    
    # 如果既没有 video_plan 也没有 segments，返回错误
    if not video_plan and not segments:
        return {
            "scenes": None,
            "error": "缺少 video_plan 或 segments，无法生成图片"
        }
    
    # 如果有 segments 但 video_plan 为空，从 segments 构建 video_plan
    if not video_plan and segments:
        # 从 segments 构建 video_plan 结构
        video_plan = {
            "canvas": state.get("video_plan", {}).get("canvas", {"width": 1080, "height": 1920}),
            "scenes": []
        }
        for seg in segments:
            video_plan["scenes"].append({
                "start": 0,
                "end": int(seg.get("duration", 4.0) * 1000000),
                "type": "image",
                "prompt": seg.get("image_prompt", ""),
                "visual_role": seg.get("scene", "scene")
            })
    
    scenes = video_plan.get("scenes", [])
    
    # 如果 video_plan 中没有 scenes，从 segments 构建
    if not scenes and segments:
        for seg in segments:
            scenes.append({
                "start": 0,
                "end": int(seg.get("duration", 4.0) * 1000000),
                "type": "image",
                "prompt": seg.get("image_prompt", ""),
                "visual_role": seg.get("scene", "scene")
            })
    
    if not scenes:
        return {
            "scenes": None,
            "error": "缺少 scenes，无法生成图片"
        }

    # 使用线程池并行生成图片
    updated_scenes = [None] * len(scenes)
    errors = []

    def generate_single_scene(i: int, scene: Dict[str, Any], client: Any) -> tuple:
        """并行生成单张图片"""
        original_prompt = scene.get("prompt", "")
        if not original_prompt:
            return i, None, f"Scene {i} 缺少 prompt"

        # 获取场景类型，用于添加位置约束
        scene_type = scene.get("visual_role", "") or scene.get("scene", "")

        # 检查是否是固定图片类型
        if original_prompt in FIXED_IMAGES:
            logger.info(f"Generating fixed image for scene {i}: {original_prompt}")
            return _handle_fixed_image(original_prompt, i, scene, client)

        prompt = _apply_style(original_prompt, scene_type=scene_type)
        logger.info(f"Generating image for scene {i} ({scene_type}): {prompt[:80]}...")

        try:
            generate_kwargs = {
                "prompt": prompt,
                "size": "2K",
                "watermark": False,
            }
            if CHARACTER_REFERENCE_IMAGE_URL:
                generate_kwargs["image"] = CHARACTER_REFERENCE_IMAGE_URL
            response = client.generate(**generate_kwargs)

            image_url = _extract_image_url(response)

            if image_url:
                # 先下载图片再上传到 OSS
                import requests as req
                resp = req.get(image_url, timeout=30)
                if resp.status_code == 200:
                    oss_url = upload_image_to_oss(resp.content, f"scene_{i}")
                    asset_url = oss_url if oss_url else image_url
                else:
                    asset_url = image_url

                updated_scene = {
                    "start": scene.get("start", 0),
                    "end": scene.get("end", 0),
                    "type": scene.get("type", "image"),
                    "visual_role": scene.get("visual_role", ""),
                    "prompt": original_prompt,
                    "asset_url": asset_url,
                    "coze_url": image_url
                }
                logger.info(f"Scene {i} asset_url: {asset_url[:60]}...")
                return i, updated_scene, None
            else:
                # 未获取到图片 URL，使用备用图片
                logger.warning(f"Scene {i} 未获取到图片 URL，使用备用图片")
                fallback_url = _fallback_image_url()
                fallback_scene = {
                    "start": scene.get("start", 0),
                    "end": scene.get("end", 0),
                    "type": scene.get("type", "image"),
                    "visual_role": scene.get("visual_role", ""),
                    "prompt": original_prompt,
                    "asset_url": fallback_url,
                    "coze_url": fallback_url,
                    "is_fallback": True
                }
                return i, fallback_scene, None

        except Exception as e:
            # 图片生成失败，使用固定图片作为备用
            logger.warning(f"Scene {i} 生成失败: {str(e)}，使用备用图片")
            fallback_url = _fallback_image_url()
            fallback_scene = {
                "start": scene.get("start", 0),
                "end": scene.get("end", 0),
                "type": scene.get("type", "image"),
                "visual_role": scene.get("visual_role", ""),
                "prompt": original_prompt,
                "asset_url": fallback_url,
                "coze_url": fallback_url,
                "is_fallback": True
            }
            return i, fallback_scene, None

    # 并行生成所有图片（最多 3 个并发）
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(generate_single_scene, i, scene, client): i
            for i, scene in enumerate(scenes)
        }

        for future in as_completed(futures):
            idx, result_scene, error = future.result()
            if error:
                errors.append(error)
                logger.error(error)
            else:
                updated_scenes[idx] = result_scene

    # 移除 None 项（失败的场景）
    valid_scenes = [s for s in updated_scenes if s is not None]

    if errors:
        return {
            "scenes": valid_scenes if valid_scenes else None,
            "image_errors": errors,
            "error": f"部分图片生成失败: {', '.join(errors[:3])}"
        }

    return {
        "scenes": valid_scenes
    }


def _extract_image_url(response) -> str:
    """从响应中提取图片 URL"""
    try:
        # 处理 SDK 返回的不同格式
        if hasattr(response, 'data') and response.data:
            if hasattr(response.data, 'image_urls') and response.data.image_urls:
                return response.data.image_urls[0]
            if isinstance(response.data, list) and len(response.data) > 0:
                item = response.data[0]
                if hasattr(item, 'url'):
                    return item.url
                if isinstance(item, dict):
                    return item.get('url', '')

        if isinstance(response, dict):
            if 'data' in response:
                data = response['data']
                if isinstance(data, dict) and 'image_urls' in data:
                    return data['image_urls'][0] if data['image_urls'] else ''
                if isinstance(data, list) and len(data) > 0:
                    return data[0].get('url', '') if isinstance(data[0], dict) else str(data[0])
            if 'image_urls' in response:
                return response['image_urls'][0] if response['image_urls'] else ''

        if isinstance(response, list) and len(response) > 0:
            item = response[0]
            if isinstance(item, dict):
                return item.get('url', '')
            if hasattr(item, 'url'):
                return item.url

        return ''
    except Exception as e:
        logger.error(f"Failed to extract image URL: {str(e)}")
        return ''
