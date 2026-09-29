"""插件配置。"""

from __future__ import annotations

from nonebot import get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    """超管自动解禁插件配置。

    环境变量 ``SUPERUSER_UNMUTE_GROUPS``：启用自动解禁的群号列表。
    留空（默认）表示所有群生效；配置后仅对列表内的群生效。

    环境变量 ``SUPERUSER_UNMUTE_POLL_ENABLED``：是否启用周期轮询兜底。
    事件驱动可能遗漏（bot 掉线、事件丢失），轮询周期性请求平台 API
    检测保护对象是否处于禁言状态并恢复。默认开启。

    环境变量 ``SUPERUSER_UNMUTE_POLL_INTERVAL``：轮询间隔（秒）。
    每轮对每个启用群调用一次 ``get_group_member_list``。
    """

    superuser_unmute_groups: list[int] = []
    superuser_unmute_poll_enabled: bool = True
    superuser_unmute_poll_interval: int = 60


plugin_config: Config = get_plugin_config(Config)

__all__ = ["Config", "plugin_config"]
