"""NoneBot 钩子：连接事件监听与心跳静默守护的编排。

按 NoneBot 文档「钩子函数」：

- ``driver.on_bot_connect`` —— Bot 连接至 NoneBot（LLBot 服务恢复）；
- ``driver.on_bot_disconnect`` —— Bot 断开连接（LLBot 服务异常）。

账号异常（账号下线但连接未断）**由心跳事件**（``meta_event/heartbeat`` 的
``status.online`` / ``status.good``）驱动，见 :mod:`.heartbeat`；本模块只负责
连接层事件与心跳静默守护任务的生命周期。

"""

from __future__ import annotations

import asyncio
import contextlib

from nonebot import get_driver, logger

# 注意：Bot 必须运行时导入——NoneBot 注册 on_bot_connect/on_bot_disconnect
# 钩子时会解析处理函数的签名注解，放进 TYPE_CHECKING 会导致 NameError。
from nonebot.adapters import Bot

from .alerter import AlertCenter
from .core import plugin_config
from .heartbeat import HeartbeatWatchdog

driver = get_driver()


class _RuntimeState:
    """告警中心、心跳守护与后台任务的持有者（避免模块级 ``global``）。"""

    def __init__(self) -> None:
        self.center: AlertCenter | None = None
        self.watchdog: HeartbeatWatchdog | None = None
        self.stop: asyncio.Event | None = None
        self.task: asyncio.Task[None] | None = None


_state = _RuntimeState()


def get_center() -> AlertCenter:
    """返回全局告警中心（懒加载单例）。"""
    if _state.center is None:
        _state.center = AlertCenter(plugin_config)
    return _state.center


def get_watchdog() -> HeartbeatWatchdog:
    """返回全局心跳守护（懒加载单例）。"""
    if _state.watchdog is None:
        _state.watchdog = HeartbeatWatchdog(get_center())
    return _state.watchdog


def is_watched(bot: Bot) -> bool:
    """该 Bot 是否在监控范围内（``LLBOT_ALERT_ACCOUNTS`` 为空表示全部）。"""
    watched = plugin_config.llbot_alert_accounts
    if not watched:
        return True
    try:
        return int(getattr(bot, "self_id", 0) or 0) in watched
    except (TypeError, ValueError):
        return False


@driver.on_startup
async def start_heartbeat_watchdog() -> None:
    """插件启动时开始心跳静默检查（已在运行时忽略重复启动）。"""
    if not plugin_config.llbot_alert_enabled:
        logger.info("llbot-alert 已停用（LLBOT_ALERT_ENABLED=false），不检查心跳")
        return
    if plugin_config.llbot_alert_heartbeat_timeout <= 0:
        logger.info("未启用心跳静默检测（LLBOT_ALERT_HEARTBEAT_TIMEOUT=0）")
        return
    if _state.task is not None and not _state.task.done():
        return
    _state.stop = asyncio.Event()
    _state.task = asyncio.create_task(get_watchdog().run(_state.stop))
    logger.info(
        "llbot-alert 心跳静默守护已启动（超时 {}s）",
        plugin_config.llbot_alert_heartbeat_timeout,
    )


@driver.on_shutdown
async def stop_heartbeat_watchdog() -> None:
    """插件停止时结束心跳静默检查任务。"""
    if _state.stop is not None:
        _state.stop.set()
    task = _state.task
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        _state.task = None


@driver.on_bot_connect
async def on_llbot_connected(bot: Bot) -> None:
    """Bot 连接：LLBot 服务恢复（若此前告警则发送恢复通知）。"""
    if not plugin_config.llbot_alert_enabled or not is_watched(bot):
        return
    self_id = str(getattr(bot, "self_id", "") or "")
    logger.info("LLBot 连接建立（账号 {}）", self_id or "-")
    get_watchdog().touch(self_id)
    await get_center().report_service(self_id=self_id, healthy=True)


@driver.on_bot_disconnect
async def on_llbot_disconnected(bot: Bot) -> None:
    """Bot 断开：LLBot 服务异常（进程崩溃、网络中断等）。"""
    if not plugin_config.llbot_alert_enabled or not is_watched(bot):
        return
    self_id = str(getattr(bot, "self_id", "") or "")
    logger.warning("LLBot 连接断开（账号 {}），判定为服务异常", self_id or "-")
    # 断开后停止对该账号的心跳静默检测，避免与连接事件重复告警。
    get_watchdog().forget(self_id)
    await get_center().report_service(
        self_id=self_id,
        healthy=False,
        reason="OneBot 连接断开（LLBot 进程异常、崩溃或网络中断）",
    )
