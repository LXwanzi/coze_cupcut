"""
工作流节点模块
"""
__all__ = ["generate_plan", "tts_synthesize", "generate_images", "create_capcut_draft"]


def __getattr__(name):
    if name == "generate_plan":
        from graphs.nodes.generate_plan import generate_plan

        return generate_plan
    if name == "tts_synthesize":
        from graphs.nodes.tts_node import tts_synthesize

        return tts_synthesize
    if name == "generate_images":
        from graphs.nodes.image_gen_node import generate_images

        return generate_images
    if name == "create_capcut_draft":
        from graphs.nodes.capcut_node import create_capcut_draft

        return create_capcut_draft
    raise AttributeError(name)
