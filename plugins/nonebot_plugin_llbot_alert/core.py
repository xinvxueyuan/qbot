"""插件配置单例（避免各模块重复解析配置）。"""

from nonebot import get_plugin_config

from .config import Config

plugin_config = get_plugin_config(Config)

__all__ = ["Config", "plugin_config"]
