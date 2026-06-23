"""
剪映草稿生成工作流测试
"""
import json
import logging
from graphs.graph import get_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_workflow():
    """测试工作流"""
    # 初始化输入
    initial_state = {
        "topic": "出国旅行酒店入住英语",
        "duration_seconds": 60,
        "style": "旅行英语",
        "canvas_width": 1080,
        "canvas_height": 1920,
        "video_plan": None,
        "audio_url": None,
        "audio_size": None,
        "scenes_generated": None,
        "success": None,
        "draft_url": None,
        "duration": None,
        "scene_count": None,
        "caption_count": None,
        "error": None
    }
    
    # 获取工作流
    graph = get_graph()
    
    # 运行工作流
    logger.info("Starting workflow...")
    result = graph.invoke(initial_state)
    
    # 输出结果
    logger.info("Workflow completed!")
    logger.info(f"Success: {result.get('success')}")
    logger.info(f"Draft URL: {result.get('draft_url')}")
    logger.info(f"Error: {result.get('error')}")
    
    # 输出最终 JSON
    output = {
        "success": result.get("success", False),
        "draft_url": result.get("draft_url"),
        "duration": result.get("duration"),
        "scene_count": result.get("scene_count"),
        "caption_count": result.get("caption_count"),
        "message": "剪映草稿已生成，请用 capcut-mate 桌面端导入剪映。" if result.get("success") else f"生成失败: {result.get('error')}"
    }
    
    print("\n=== 最终输出 ===")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    
    return output


if __name__ == "__main__":
    test_workflow()
