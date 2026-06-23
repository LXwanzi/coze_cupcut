"""
AI 图片生成节点
输入: video_plan
输出: scenes（每项包含 asset_url）
"""
import logging
from typing import Dict, Any
from coze_coding_dev_sdk import ImageGenerationClient
from coze_coding_utils.runtime_ctx.context import new_context

logger = logging.getLogger(__name__)


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
        prompt = scene.get("prompt", "")
        if not prompt:
            errors.append(f"Scene {i} 缺少 prompt")
            continue

        try:
            # 生成 9:16 竖屏图片
            response = client.generate(
                prompt=prompt,
                size="2K",
                watermark=False
            )

            if response.success and response.image_urls:
                scene["asset_url"] = response.image_urls[0]
                logger.info(f"Scene {i} generated: {scene['asset_url']}")
            else:
                error_msg = f"Scene {i} 生成失败: {response.error_messages}"
                errors.append(error_msg)
                logger.error(error_msg)
                continue

        except Exception as e:
            error_msg = f"Scene {i} 异常: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            continue

        updated_scenes.append(scene)

    if errors and not updated_scenes:
        return {
            "scenes": None,
            "error": f"所有图片生成失败: {'; '.join(errors)}"
        }

    # 更新 video_plan 中的 scenes
    video_plan["scenes"] = updated_scenes

    logger.info(f"Generated {len(updated_scenes)} images for {len(scenes)} scenes")

    return {
        "video_plan": video_plan,
        "scenes_generated": len(updated_scenes),
        "errors": errors if errors else None,
        "error": None
    }
