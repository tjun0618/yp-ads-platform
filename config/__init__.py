# -*- coding: utf-8 -*-
"""
config/__init__.py
==================
配置模块

使用方式:
    from config import config

    settings = config.load_settings()
    agent = config.load_agent("ad_creator")
    skill_content = config.load_skill_content("google-ads-v5.0")
"""

from .loader import ConfigLoader, config

__all__ = ["ConfigLoader", "config"]
