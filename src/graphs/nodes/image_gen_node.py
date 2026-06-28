"""
AI 图片生成节点
输入: video_plan
输出: scenes（每项包含 asset_url）

图片风格：极简卡通圆头豆豆人「小丸子」，白色或浅色干净背景，
线条简洁，表情亲切有活力，像利用碎片时间学英语的年轻打工人学习搭子。
画面元素少，主体明确，底部预留字幕区域，色彩明亮，扁平化插画风格。
竖屏比例 9:16，适合 1080x1920 视频。

复习页使用固定复习卡背景图，不生成AI图片。

生成后自动上传到 OSS，CapCut Mate 可直接访问。
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

# 小丸子角色参考图 URL（上传到 OSS 后的永久 URL）
CHARACTER_REFERENCE_IMAGE_URL = (
    "https://coze-coding-project.tos.coze.site/"
    "coze_storage_7654517760407470089/character/xiaowanzi_reference_025ac01d.png"
    "?sign=1813840450-6d264531cf-0-98731a4230b5a6d4f921455f1f0f76e47a690a7e486f6a0e53b2c4637f455532"
)

# 固定图片 URL（warm beige背景 + 米白色渐变）
FIXED_HOOK_IMAGE_URL = (
    "https://coze-coding-project.tos.coze.site/"
    "coze_storage_7654517760407470089/fixed/hook_v2_c362fa07.png"
    "?sign=1784964895-037cf37b48-0-339cc160f1c31a11dedb04c065cf435541bf41677ce811b2332fdd1d4cf6fd12"
)

# 复习卡带人物背景 URL（底部小头像，顶部80%留白给字幕）
FIXED_REVIEW_WITH_CHAR_URL = (
    "https://coze-coding-project.tos.coze.site/"
    "coze_storage_7654517760407470089/fixed/review_v2_6f1121be.png"
    "?sign=1784964896-cd489dffc6-0-6cfcc2b6b884fc6aa2e4685b6e97081a2d8125a2e1967f3c16da1b9b8e22dd81"
)

# 缓存已生成的固定图片（仅用于缓存从 URL 下载后的本地路径）
FIXED_HOOK_IMAGE_GENERATED = None
FIXED_REVIEW_BACKGROUND_GENERATED = None

# 统一图片风格后缀（warm beige米白色渐变背景，顶部15%留白给字幕）
STYLE_SUFFIX = (
    ", warm beige gradient background, minimalist style, soft lighting. "
    "The top 15% of the frame is completely empty and clean for text overlay. "
    "Minimalist round-headed cartoon character Xiao Wanzi, young office worker "
    "learning English in everyday spare moments, wearing wireless earbuds and carrying a laptop bag, "
    "short black hair, light-colored top, crossbody bag, line art style, "
    "character prominently displayed in center of frame, large and clear, "
    "taking up about 40-50% of the image height, positioned vertically centered, "
    "no text inside the image, bright colors, flat illustration, 9:16 vertical frame"
)

# 禁止的风格/颜色关键词
FORBIDDEN_STYLES = [
    # 禁止的质感
    "photorealistic", "realistic photo", "cinematic", "film grain",
    "hyperrealistic", "detailed texture", "3D render", "cyberpunk",
    "dark style", "oil painting", "complex background", "anime",
    "manga", "children book", "childish", "text in image",
    # 禁止的蓝色系背景
    "blue", "cyan", "sky blue", "gradient blue", "teal", "navy",
    "azure", "ocean blue", "light blue", "dark blue", "royal blue",
    "aqua", "turquoise", "steel blue", "cobalt", "indigo"
]


def _handle_fixed_image(prompt_marker: str, i: int, scene: Dict[str, Any], client: Any) -> tuple:
    """处理固定图片类型：直接使用预置固定 URL，不调用 API"""
    global FIXED_HOOK_IMAGE_GENERATED, FIXED_REVIEW_BACKGROUND_GENERATED

    try:
        if prompt_marker == "FIXED_HOOK_IMAGE":
            fixed_url = FIXED_HOOK_IMAGE_URL
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
            fixed_url = FIXED_REVIEW_WITH_CHAR_URL
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
            # 纯色渐变复习背景（无人物）
            import requests as req
            fixed_url = (
                "https://coze-coding-project.tos.coze.site/"
                "coze_storage_7654517760407470089/fixed/review_bg_a6d431c4.png"
                "?sign=xxx"
            )
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
        position_constraint = (
            ", IMPORTANT: Xiao Wanzi MUST be positioned in the BOTTOM-LEFT or BOTTOM-RIGHT corner, "
            "character height takes up NO MORE than 30% of the frame height, "
            "right side and upper area of the frame (60%+) MUST be completely empty for subtitle text overlay, "
            "background is a clean review card style with large empty space on the right"
        )
    elif "标题页" in scene_type:
        # 标题页：人物在中下，头顶留白
        position_constraint = (
            ", IMPORTANT: Xiao Wanzi positioned in the CENTER-LOWER area, "
            "top 25% of the frame is intentionally left empty and clean for subtitle placement, "
            "character head should NOT reach the middle of the frame"
        )
    else:
        # 跟读句：人物固定在中下区域
        position_constraint = (
            ", IMPORTANT: Xiao Wanzi positioned in the CENTER-LOWER or LOWER-CENTER area of the frame, "
            "top 25% of the frame is intentionally left empty and clean for subtitle placement, "
            "character head should NOT reach the top third of the frame"
        )

    # 构建完整 prompt（STYLE_SUFFIX 已包含角色一致性描述）
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
        if original_prompt in ("FIXED_HOOK_IMAGE", "FIXED_REVIEW_WITH_CHAR"):
            logger.info(f"Generating fixed image for scene {i}: {original_prompt}")
            return _handle_fixed_image(original_prompt, i, scene, client)

        prompt = _apply_style(original_prompt, scene_type=scene_type)
        logger.info(f"Generating image for scene {i} ({scene_type}): {prompt[:80]}...")

        try:
            response = client.generate(
                prompt=prompt,
                size="2K",
                watermark=False,
                image=CHARACTER_REFERENCE_IMAGE_URL
            )

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
                fallback_url = FIXED_HOOK_IMAGE_URL
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
            fallback_url = FIXED_HOOK_IMAGE_URL  # 使用钩子图作为备用
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
