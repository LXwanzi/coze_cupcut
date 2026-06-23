"""
AI 图片生成节点
输入: video_plan
输出: scenes（每项包含 asset_url）

图片风格：极简卡通火柴人风格，白色或浅色干净背景，
线条简洁，人物用火柴人或简化卡通小人表现，表情夸张但可爱，
画面元素少，主体明确，色彩明亮，扁平化插画风格。
竖屏比例 9:16，适合 1080x1920 视频。
"""
import logging
from typing import Dict, Any
from coze_coding_dev_sdk import ImageGenerationClient
from coze_coding_utils.runtime_ctx.context import new_context

logger = logging.getLogger(__name__)

# 统一图片风格后缀
STYLE_SUFFIX = (
    ", minimalist stick figure cartoon style, white or light clean background, "
    "simple clean lines, stick figure or simplified cartoon character, "
    "exaggerated cute expressions, minimal elements in frame, clear main subject, "
    "bright colors, flat illustration style, 9:16 vertical frame"
)

# 禁止的风格关键词
FORBIDDEN_STYLES = [
    "photorealistic", "realistic photo", "cinematic", "film grain",
    "hyperrealistic", "detailed texture", "3D render", "cyberpunk",
    "dark style", "oil painting", "complex background"
]


def _apply_style(prompt: str) -> str:
    """为 prompt 添加统一风格，并移除禁止的风格关键词"""
    # 移除禁止的关键词
    clean_prompt = prompt
    for forbidden in FORBIDDEN_STYLES:
        clean_prompt = clean_prompt.replace(forbidden, "")

    # 添加风格后缀
    return clean_prompt + STYLE_SUFFIX


def generate_images(state: Dict[str, Any]) -> Dict[str, Any]:
    """为所有 scenes 生成 AI 图片"""
    ctx = new_context(method="generate_images")
    client = ImageGenerationClient(ctx=ctx)

    # 优先使用 video_plan
    video_plan = state.get("video_plan")
    if not video_plan:
        return {
            "scenes": None,
            "error": "缺少 video_plan，无法生成图片"
        }

    scenes = video_plan.get("scenes", [])
    if not scenes:
        return {
            "scenes": None,
            "error": "video_plan 中缺少 scenes"
        }

    updated_scenes = []
    errors = []

    for i, scene in enumerate(scenes):
        original_prompt = scene.get("prompt", "")
        if not original_prompt:
            errors.append(f"Scene {i} 缺少 prompt")
            continue

        # 应用统一风格
        prompt = _apply_style(original_prompt)
        logger.info(f"Generating image for scene {i}: {prompt[:100]}...")

        try:
            # 生成 2K 竖屏图片
            response = client.generate(
                prompt=prompt,
                size="2K",
                watermark=False
            )

            # 提取图片 URL
            image_url = _extract_image_url(response)

            if image_url:
                # 构建带 asset_url 的 scene
                updated_scene = {
                    "start": scene.get("start", 0),
                    "end": scene.get("end", 0),
                    "type": scene.get("type", "image"),
                    "visual_role": scene.get("visual_role", ""),
                    "prompt": original_prompt,  # 保留原始 prompt
                    "asset_url": image_url
                }
                updated_scenes.append(updated_scene)
                logger.info(f"Scene {i} image generated: {image_url[:80]}...")
            else:
                errors.append(f"Scene {i} 未获取到图片 URL")
                logger.error(f"Scene {i} image generation failed: {response}")

        except Exception as e:
            errors.append(f"Scene {i} 生成失败: {str(e)}")
            logger.error(f"Scene {i} exception: {str(e)}")

    if errors:
        return {
            "scenes": updated_scenes if updated_scenes else None,
            "image_errors": errors,
            "error": f"部分图片生成失败: {', '.join(errors)}"
        }

    return {
        "scenes": updated_scenes
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
