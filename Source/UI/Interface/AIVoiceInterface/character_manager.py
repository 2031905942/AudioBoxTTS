"""
角色管理器

负责角色数据的 CRUD 操作和 JSON 持久化。
角色数据存储在本地 config/characters.json，不纳入版本控制。
"""
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict


@dataclass
class Character:
    """角色数据类"""
    id: str
    name: str
    avatar_path: str = ""  # 头像图片路径（本地）
    reference_audio_path: str = ""  # 音色参考音频路径
    last_output_dir: str = ""  # 上次输出目录
    last_output_filename: str = ""  # 上次输出文件名
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    @staticmethod
    def create(name: str, avatar_path: str = "") -> "Character":
        """创建新角色"""
        return Character(
            id=str(uuid.uuid4()),
            name=name,
            avatar_path=avatar_path,
            created_at=datetime.now().isoformat()
        )
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: Dict) -> "Character":
        """从字典创建"""
        return Character(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "未命名"),
            avatar_path=data.get("avatar_path", ""),
            reference_audio_path=data.get("reference_audio_path", ""),
            last_output_dir=data.get("last_output_dir", ""),
            last_output_filename=data.get("last_output_filename", ""),
            created_at=data.get("created_at", datetime.now().isoformat())
        )


class CharacterManager:
    """角色管理器"""
    
    MAX_CHARACTERS = 20  # 最大角色数量
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化角色管理器
        
        Args:
            config_dir: 配置文件目录，默认为项目根目录的 config 文件夹
        """
        if config_dir is None:
            # 默认使用项目根目录的 config 文件夹
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
            config_dir = os.path.join(project_root, "config")
        
        self._config_dir = config_dir
        self._json_path = os.path.join(config_dir, "characters.json")
        self._characters: List[Character] = []
        self._selected_id: Optional[str] = None
        
        self._load()
    
    @property
    def characters(self) -> List[Character]:
        """获取所有角色"""
        return self._characters.copy()
    
    @property
    def selected_character(self) -> Optional[Character]:
        """获取当前选中的角色"""
        if not self._selected_id:
            return None
        return self.get_by_id(self._selected_id)
    
    @property
    def selected_id(self) -> Optional[str]:
        """获取当前选中角色的 ID"""
        return self._selected_id
    
    @property
    def count(self) -> int:
        """获取角色数量"""
        return len(self._characters)
    
    @property
    def can_add(self) -> bool:
        """是否可以添加新角色"""
        return len(self._characters) < self.MAX_CHARACTERS
    
    def _load(self):
        """从 JSON 文件加载角色数据"""
        if not os.path.exists(self._json_path):
            self._characters = []
            self._selected_id = None
            return
        
        try:
            with open(self._json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._characters = [
                Character.from_dict(c) for c in data.get("characters", [])
            ]
            self._selected_id = data.get("selected_character_id")
            
            # 验证选中的角色是否存在
            if self._selected_id and not self.get_by_id(self._selected_id):
                self._selected_id = None
                
        except (json.JSONDecodeError, IOError) as e:
            print(f"[CharacterManager] 加载角色数据失败: {e}")
            self._characters = []
            self._selected_id = None
    
    def _save(self):
        """保存角色数据到 JSON 文件"""
        os.makedirs(self._config_dir, exist_ok=True)
        
        data = {
            "characters": [c.to_dict() for c in self._characters],
            "selected_character_id": self._selected_id
        }
        
        try:
            with open(self._json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"[CharacterManager] 保存角色数据失败: {e}")
    
    def get_by_id(self, character_id: str) -> Optional[Character]:
        """根据 ID 获取角色"""
        for c in self._characters:
            if c.id == character_id:
                return c
        return None
    
    def add(self, name: str, avatar_path: str = "") -> Optional[Character]:
        """
        添加新角色
        
        Args:
            name: 角色名称
            avatar_path: 头像路径
            
        Returns:
            新创建的角色，如果超过上限则返回 None
        """
        if not self.can_add:
            return None
        
        character = Character.create(name, avatar_path)
        self._characters.append(character)
        
        # 如果是第一个角色，自动选中
        if len(self._characters) == 1:
            self._selected_id = character.id
        
        self._save()
        return character
    
    def update(self, character_id: str, **kwargs) -> bool:
        """
        更新角色信息
        
        Args:
            character_id: 角色 ID
            **kwargs: 要更新的字段
            
        Returns:
            是否更新成功
        """
        character = self.get_by_id(character_id)
        if not character:
            return False
        
        for key, value in kwargs.items():
            if hasattr(character, key):
                setattr(character, key, value)
        
        self._save()
        return True
    
    def delete(self, character_id: str) -> bool:
        """
        删除角色
        
        Args:
            character_id: 角色 ID
            
        Returns:
            是否删除成功
        """
        character = self.get_by_id(character_id)
        if not character:
            return False
        
        self._characters.remove(character)
        
        # 如果删除的是当前选中的角色，重置选中状态
        if self._selected_id == character_id:
            self._selected_id = self._characters[0].id if self._characters else None
        
        self._save()
        return True
    
    def select(self, character_id: str) -> bool:
        """
        选中角色
        
        Args:
            character_id: 角色 ID
            
        Returns:
            是否选中成功
        """
        if not self.get_by_id(character_id):
            return False
        
        self._selected_id = character_id
        self._save()
        return True
    
    def move_to_top(self, character_id: str) -> bool:
        """
        将角色移动到列表顶部（置顶）
        
        Args:
            character_id: 角色 ID
            
        Returns:
            是否移动成功
        """
        character = self.get_by_id(character_id)
        if not character:
            return False
        
        # 从当前位置移除
        self._characters.remove(character)
        # 插入到列表开头
        self._characters.insert(0, character)
        
        self._save()
        return True
    
    def select_and_move_to_top(self, character_id: str) -> bool:
        """
        选中角色并置顶
        
        Args:
            character_id: 角色 ID
            
        Returns:
            是否成功
        """
        if not self.move_to_top(character_id):
            return False
        return self.select(character_id)

    def update_reference_audio(self, character_id: str, audio_path: str) -> bool:
        """更新角色的参考音频"""
        return self.update(character_id, reference_audio_path=audio_path)
    
    def update_last_output(self, character_id: str, output_dir: str, filename: str) -> bool:
        """更新角色的上次输出路径"""
        return self.update(
            character_id,
            last_output_dir=output_dir,
            last_output_filename=filename
        )
    
    def get_suggested_output_path(self, character_id: str) -> tuple[str, str]:
        """
        获取建议的输出路径
        
        Returns:
            (目录, 文件名) 元组
        """
        character = self.get_by_id(character_id)
        if not character:
            return "", ""
        
        output_dir = character.last_output_dir
        filename = character.last_output_filename
        
        # 如果没有上次路径，使用默认值
        if not output_dir:
            from PySide6.QtCore import QStandardPaths
            output_dir = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.MusicLocation
            )
        
        if not filename:
            import time
            filename = f"{character.name}_{int(time.time())}.wav"
        
        return output_dir, filename
