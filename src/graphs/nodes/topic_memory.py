"""
专题记忆表管理模块

用于存储每个专题的历史记录，实现"追剧式"连续内容生成。
"""

import json
import os
from typing import Optional
from datetime import datetime


def _get_memory_dir() -> str:
    """Resolve memory directory at runtime for Coze and local tests."""
    return os.path.join(os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects"), "assets", "topic_memory")


class TopicMemory:
    """专题记忆表"""
    
    def __init__(self, topic_id: str):
        self.topic_id = topic_id
        self.data = self._load()
    
    def _get_file_path(self) -> str:
        """获取记忆表文件路径"""
        memory_dir = _get_memory_dir()
        os.makedirs(memory_dir, exist_ok=True)
        return os.path.join(memory_dir, f"{self.topic_id}.json")
    
    def _load(self) -> dict:
        """加载记忆表"""
        path = self._get_file_path()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self._create_empty()
    
    def _create_empty(self) -> dict:
        """创建空记忆表"""
        return {
            "topic_id": self.topic_id,
            "season_name": "",
            "episodes": [],
            "all_sentences": [],
            "scenes_used": [],
            "pain_points_used": [],
            "wrong_expressions_used": [],
            "last_hook": "",
            "next_preview": "",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    
    def save(self):
        """保存记忆表"""
        self.data["updated_at"] = datetime.now().isoformat()
        path = self._get_file_path()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    @property
    def episode_count(self) -> int:
        """当前集数"""
        return len(self.data["episodes"])
    
    @property
    def next_episode_num(self) -> int:
        """下一集编号"""
        return self.episode_count + 1
    
    @property
    def all_sentences(self) -> list:
        """所有已学句子"""
        return self.data["all_sentences"]
    
    @property
    def scenes_used(self) -> list:
        """已用场景"""
        return self.data["scenes_used"]
    
    @property
    def last_episode(self) -> Optional[dict]:
        """上一集信息"""
        if self.data["episodes"]:
            return self.data["episodes"][-1]
        return None
    
    @property
    def next_preview(self) -> str:
        """下一集预告"""
        return self.data.get("next_preview", "")
    
    def add_episode(self, episode_data: dict):
        """添加新一集"""
        episode = {
            "episode_num": self.next_episode_num,
            "sentences": episode_data.get("sentences", []),
            "scene": episode_data.get("scene", ""),
            "hook": episode_data.get("hook", ""),
            "preview": episode_data.get("preview", ""),
            "pain_point": episode_data.get("pain_point", ""),
            "wrong_expression": episode_data.get("wrong_expression", ""),
            "answer_levels": episode_data.get("answer_levels", []),
            "created_at": datetime.now().isoformat()
        }
        
        self.data["episodes"].append(episode)
        
        # 更新已学句子
        for s in episode["sentences"]:
            if s not in self.data["all_sentences"]:
                self.data["all_sentences"].append(s)
        
        # 更新已用场景
        if episode["scene"] and episode["scene"] not in self.data["scenes_used"]:
            self.data["scenes_used"].append(episode["scene"])

        pain_point = episode.get("pain_point")
        if pain_point and pain_point not in self.data.setdefault("pain_points_used", []):
            self.data["pain_points_used"].append(pain_point)

        wrong_expression = episode.get("wrong_expression")
        if wrong_expression and wrong_expression not in self.data.setdefault("wrong_expressions_used", []):
            self.data["wrong_expressions_used"].append(wrong_expression)
        
        # 更新下一集预告
        self.data["next_preview"] = episode.get("preview", "")
        
        self.save()
    
    def set_season_name(self, name: str):
        """设置专题名称"""
        self.data["season_name"] = name
        self.save()
    
    def get_context_for_plan(self) -> dict:
        """获取用于生成计划的上下文"""
        last_ep = self.last_episode
        return {
            "topic_id": self.topic_id,
            "season_name": self.data.get("season_name", ""),
            "episode_num": self.next_episode_num,
            "has_previous": last_ep is not None,
            "last_sentences": last_ep["sentences"] if last_ep else [],
            "last_scene": last_ep["scene"] if last_ep else "",
            "last_preview": self.data.get("next_preview", ""),
            "all_sentences": self.data["all_sentences"],
            "scenes_used": self.data["scenes_used"],
            "used_pain_points": self.data.get("pain_points_used", []),
            "wrong_expressions_used": self.data.get("wrong_expressions_used", []),
        }


def get_topic_memory(topic_id: str) -> TopicMemory:
    """获取专题记忆表"""
    return TopicMemory(topic_id)


def list_topics() -> list:
    """列出所有专题"""
    memory_dir = _get_memory_dir()
    os.makedirs(memory_dir, exist_ok=True)
    topics = []
    for f in os.listdir(memory_dir):
        if f.endswith('.json'):
            topic_id = f[:-5]
            memory = TopicMemory(topic_id)
            topics.append({
                "topic_id": topic_id,
                "season_name": memory.data.get("season_name", ""),
                "episode_count": memory.episode_count
            })
    return topics


def clear_all_topics():
    """清除所有专题记忆（用于测试）"""
    import shutil
    memory_dir = _get_memory_dir()
    if os.path.exists(memory_dir):
        shutil.rmtree(memory_dir)
