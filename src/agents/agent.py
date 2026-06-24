"""
通勤英语内容助手 Agent
把每日英语学习笔记转化为原创短视频内容
"""
from graphs.graph import get_graph


def build_agent(ctx=None):
    """
    Coze agent 项目的兼容入口。

    这个项目本质是一个工作流，不是 messages 驱动的聊天 Agent。部分
    Coze 运行环境会因为存在 src/agents/agent.py 而按 agent 项目加载，
    所以这里返回同一张已编译的 LangGraph，避免入口类型不一致。
    """
    return get_graph()
