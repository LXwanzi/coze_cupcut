"""
AI 图片生成节点
输入: video_plan
输出: scenes（每项包含 asset_url）

图片风格：极简卡通圆头豆豆人「小丸子」，白色或浅色干净背景，
线条简洁，表情亲切有活力，像利用碎片时间学英语的年轻打工人学习搭子。
画面元素少，主体明确，底部预留字幕区域，色彩明亮，扁平化插画风格。
竖屏比例 9:16，适合 1080x1920 视频。

生成后自动上传到 OSS，CapCut Mate 可直接访问。
"""
import logging
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from coze_coding_dev_sdk import ImageGenerationClient
from coze_coding_utils.runtime_ctx.context import new_context
from graphs.nodes.oss_uploader import upload_image_to_oss

logger = logging.getLogger(__name__)

# 小丸子角色参考图 URL（上传到 OSS 后的永久 URL）
CHARACTER_REFERENCE_IMAGE_URL = (
    "https://coze-coding-project.tos.coze.site/"
    "coze_storage_7654517760407470089/character/xiaowanzi_reference_025ac01d.png"
    "?sign=1813840450-6d264531cf-0-98731a4230b5a6d4f921455f1f0f76e47a690a7e486f6a0e53b2c4637f455532"
)

# 统一图片风格后缀（角色一致性要求）
STYLE_SUFFIX = (
    ", minimalist round-headed cartoon character Xiao Wanzi, young office worker "
    "learning English in everyday spare moments, wearing wireless earbuds and carrying a laptop bag, "
    "white or light clean background, simple black outlines, warm energetic expression, "
    "minimal details, clear main subject occupying 50-65% of the frame, "
    "bottom 25% of the image intentionally left clean for subtitles, "
    "no text inside the image, no large empty areas outside the subtitle area, "
    "bright colors, flat illustration, 9:16 vertical frame"
)

# 角色一致性追加描述（用于图生图）
CHARACTER_CONSISTENCY_PROMPT = (
    " Keep the character consistent with the reference image: "
    "same face shape, short black hair, wireless earbuds, light-colored top, crossbody bag, line art style. "
    "Only change actions, expressions, props and scene. "
    "Do not generate character sheet text, labels, borders, or multiple characters."
)

# 禁止的风格关键词
FORBIDDEN_STYLES = [
    "photorealistic", "realistic photo", "cinematic", "film grain",
    "hyperrealistic", "detailed texture", "3D render", "cyberpunk",
    "dark style", "oil painting", "complex background", "anime",
    "manga", "children book", "childish", "text in image"
]


def _apply_style(prompt: str, use_reference: bool = True) -> str:
    """为 prompt 添加统一风格，并移除禁止的风格关键词
    
    Args:
        prompt: 原始 prompt
        use_reference: 是否追加角色一致性描述
    """
    # 移除禁止的关键词
    clean_prompt = prompt
    for forbidden in FORBIDDEN_STYLES:
        clean_prompt = clean_prompt.replace(forbidden, "")

    # 添加风格后缀
    styled_prompt = clean_prompt + STYLE_SUFFIX
    
    # 追加角色一致性描述（图生图模式）
    if use_reference:
        styled_prompt += CHARACTER_CONSISTENCY_PROMPT
    
    return styled_prompt


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

        prompt = _apply_style(original_prompt)
        logger.info(f"Generating image for scene {i}: {prompt[:80]}...")

        try:
            response = client.generate(
                prompt=prompt,
                size="2K",
                watermark=False,
                image=CHARACTER_REFERENCE_IMAGE_URL
            )

            image_url = _extract_image_url(response)

            if image_url:
                oss_url = upload_image_to_oss(image_url, i)
                asset_url = oss_url if oss_url else image_url

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
                return i, None, f"Scene {i} 未获取到图片 URL"

        except Exception as e:
            return i, None, f"Scene {i} 生成失败: {str(e)}"

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
