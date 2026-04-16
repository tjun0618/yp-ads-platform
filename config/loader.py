# -*- coding: utf-8 -*-
"""
config/loader.py
================
配置加载器

功能:
- 加载 YAML 配置文件
- 环境变量替换
- 配置缓存
- 技能文件加载

使用:
    from config import config
    
    settings = config.load_settings()
    agent = config.load_agent("ad_creator")
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, config_dir: str = None):
        """
        初始化配置加载器
        
        Args:
            config_dir: 配置目录路径，默认为当前文件所在目录
        """
        if config_dir is None:
            config_dir = Path(__file__).parent
        self.config_dir = Path(config_dir)
        self._cache: Dict[str, Any] = {}
    
    def load_settings(self) -> Dict[str, Any]:
        """加载全局设置"""
        return self._load_yaml("settings.yaml")
    
    def load_agents(self) -> Dict[str, Any]:
        """加载所有 Agent 配置"""
        return self._load_yaml("agents.yaml").get("agents", {})
    
    def load_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        加载单个 Agent 配置
        
        Args:
            agent_id: Agent ID (如 "ad_creator")
        
        Returns:
            Agent 配置字典，不存在返回 None
        """
        agents = self.load_agents()
        return agents.get(agent_id)
    
    def load_skills(self) -> Dict[str, Any]:
        """加载所有技能配置"""
        return self._load_yaml("skills.yaml").get("skills", {})
    
    def load_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        加载单个技能配置
        
        Args:
            skill_id: 技能 ID (如 "google-ads-v5.0")
        
        Returns:
            技能配置字典，不存在返回 None
        """
        skills = self.load_skills()
        return skills.get(skill_id)
    
    def load_tools(self) -> Dict[str, Any]:
        """加载所有工具配置"""
        return self._load_yaml("tools.yaml").get("tools", {})
    
    def load_tool(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """
        加载单个工具配置
        
        Args:
            tool_id: 工具 ID (如 "db_query")
        
        Returns:
            工具配置字典，不存在返回 None
        """
        tools = self.load_tools()
        return tools.get(tool_id)
    
    def load_skill_content(self, skill_id: str) -> str:
        """
        加载技能文件内容（包含参考文件）
        
        Args:
            skill_id: 技能 ID
        
        Returns:
            技能文件完整内容
        """
        skill_config = self.load_skill(skill_id)
        if not skill_config:
            raise ValueError(f"Skill not found: {skill_id}")
        
        # 获取技能文件路径
        skill_path = skill_config.get("path", "")
        if not skill_path:
            raise ValueError(f"Skill {skill_id} has no path defined")
        
        skill_path = Path(skill_path)
        if not skill_path.is_absolute():
            # 相对于项目根目录
            skill_path = self.config_dir.parent / skill_path
        
        if not skill_path.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_path}")
        
        # 读取主文件
        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 读取参考文件
        references = skill_config.get("references", [])
        if references:
            refs_dir = skill_path.parent / "references"
            for ref_file in references:
                ref_path = refs_dir / ref_file
                if ref_path.exists():
                    with open(ref_path, "r", encoding="utf-8") as f:
                        ref_content = f.read()
                    content += f"\n\n---\n\n## {ref_file}\n\n{ref_content}"
        
        return content
    
    def load_prompt(self, prompt_type: str, name: str) -> str:
        """
        加载提示词模板
        
        Args:
            prompt_type: 提示词类型 (system / user)
            name: 模板名称
        
        Returns:
            模板内容
        """
        prompt_path = self.config_dir / "prompts" / prompt_type / f"{name}.md"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt not found: {prompt_path}")
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    
    def get_llm_config(self) -> Dict[str, Any]:
        """获取 LLM 配置"""
        settings = self.load_settings()
        return settings.get("llm", {})
    
    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        settings = self.load_settings()
        return settings.get("database", {})
    
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
    
    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """
        加载 YAML 文件（带缓存）
        
        Args:
            filename: 文件名
        
        Returns:
            解析后的字典
        """
        if filename in self._cache:
            return self._cache[filename]
        
        filepath = self.config_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Config file not found: {filepath}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        # 环境变量替换
        data = self._replace_env_vars(data)
        
        self._cache[filename] = data
        return data
    
    def _replace_env_vars(self, obj: Any) -> Any:
        """
        递归替换环境变量 ${VAR_NAME}
        
        Args:
            obj: 要处理的对象
        
        Returns:
            替换后的对象
        """
        if isinstance(obj, str):
            if obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                return os.environ.get(var_name, obj)
            return obj
        elif isinstance(obj, dict):
            return {k: self._replace_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_env_vars(item) for item in obj]
        return obj
    
    def __repr__(self) -> str:
        return f"ConfigLoader(config_dir={self.config_dir})"


# 全局配置实例
config = ConfigLoader()
