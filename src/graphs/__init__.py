"""
工作流图模块
"""

__all__ = [
    "get_graph",
    "build_graph",
    "create_workflow",
    "VideoWorkflowState"
]


def __getattr__(name):
    if name in __all__:
        from graphs import graph

        return getattr(graph, name)
    raise AttributeError(name)
