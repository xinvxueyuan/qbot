"""心跳事件：从 OneBot 心跳抽取账号状态（不再轮询 HTTP 接口）。

LLBot（ws-reverse）每 ``interval`` 毫秒推送一次心跳，事件结构::

    {"post_type": "meta_event", "meta_event_type": "heartbeat",
     "self_id": 123456789, "time": 1640995200, "interval": 6000,
     "status": {"online": true, "good": true}}

``status.online`` 表示账号是否在线、``status.good`` 表示状态是否良好——这正是
「账号异常（账号下线）」的判据，且随心跳持续到达，因此**无需再轮询**
``POST /get_status``。

另设「心跳静默守护」：连接仍在但超过 ``LLBOT_ALERT_HEARTBEAT_TIMEOUT`` 秒
未收到任何心跳时判定为服务异常（连接假死或事件通道阻塞），这比单纯依赖
连接断开事件更早发现问题。

"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from nonebot import logger, on_type

# 心跳处理函数是 NoneBot 事件处理器，签名注解会在运行时被解析，故 Bot 需
# 运行时导入（放入 TYPE_CHECKING 会 NameError，与 hooks.py 同理）。
from nonebot.adapters.onebot.v11 import Bot as OneBot11Bot
from nonebot.adapters.onebot.v11.event import HeartbeatMetaEvent

from .core import plugin_config
from .models import BotStatus

if TYPE_CHECKING:
    from .alerter import AlertCenter

#: 心跳事件响应器（低优先级且不阻断，避免影响其他插件）。
heartbeat = on_type(HeartbeatMetaEvent, priority=1, block=False)

_MIN_CHECK_INTERVAL = 5


def status_from_event(event: HeartbeatMetaEvent) -> BotStatus:
    """从心跳事件抽取账号状态。

    Args:
        event: OneBot 心跳事件。

    Returns:
        账号状态；``status`` 缺失时按不健康处理（宁可告警不可漏报）。

    """
    status = getattr(event, "status", None)
    online = getattr(status, "online", None)
    good = getattr(status, "good", None)
    if online is None and good is None:
        return BotStatus(online=False, good=False, message="心跳缺少 status 字段")
    return BotStatus(online=bool(online), good=bool(good))


class HeartbeatWatchdog:
    """记录各账号的最后心跳时间，用于检测心跳静默。"""

    def __init__(self, center: AlertCenter) -> None:
        """初始化守护器。

        Args:
            center: 告警中心。

        """
        self._center = center
        self._last_seen: dict[str, datetime] = {}

    def touch(self, self_id: str) -> None:
        """记录一次心跳到达（首次记录时打日志，便于确认检测链路生效）。"""
        first_seen = self_id not in self._last_seen
        self._last_seen[self_id] = datetime.now(UTC)
        if first_seen:
            logger.info("已收到账号 {} 的心跳，账号状态检测链路生效", self_id or "-")

    def last_seen(self, self_id: str) -> datetime | None:
        """返回某账号最后一次心跳时间。"""
        return self._last_seen.get(self_id)

    def silent_accounts(self, timeout: int, now: datetime) -> list[str]:
        """返回心跳静默超过 ``timeout`` 秒的账号列表。"""
        return [
            self_id
            for self_id, seen in self._last_seen.items()
            if (now - seen).total_seconds() >= timeout
        ]

    def forget(self, self_id: str) -> None:
        """清除某账号的心跳记录（断开连接后由连接事件接管）。"""
        self._last_seen.pop(self_id, None)

    async def check_once(self) -> None:
        """检查一次静默情况并对超时账号上报服务异常。"""
        timeout = plugin_config.llbot_alert_heartbeat_timeout
        if timeout <= 0:
            return
        for self_id in self.silent_accounts(timeout, datetime.now(UTC)):
            logger.warning("账号 {} 心跳静默超过 {}s，判定为服务异常", self_id, timeout)
            self.forget(self_id)
            await self._center.report_service(
                self_id=self_id,
                healthy=False,
                reason=f"心跳静默超过 {timeout} 秒（连接假死或事件通道阻塞）",
            )

    async def run(self, stop: asyncio.Event) -> None:
        """周期性执行静默检查，直到 ``stop`` 被置位。"""
        interval = max(
            _MIN_CHECK_INTERVAL,
            plugin_config.llbot_alert_check_interval,
        )
        while not stop.is_set():
            try:
                await self.check_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - 单次检查失败不应终止守护
                logger.exception("心跳静默检查出现未预期异常")
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except TimeoutError:
                continue


@heartbeat.handle()
async def on_heartbeat(bot: OneBot11Bot, event: HeartbeatMetaEvent) -> None:
    """心跳到达：抽取 status 上报账号状态，并刷新静默计时。"""
    from .hooks import get_center, get_watchdog, is_watched  # 延迟导入避免环依赖

    if not plugin_config.llbot_alert_enabled or not is_watched(bot):
        return
    self_id = str(getattr(event, "self_id", "") or "")
    status = status_from_event(event)
    get_watchdog().touch(self_id)
    if not status.healthy:
        logger.warning(
            "心跳显示账号异常: self_id={} online={} good={}",
            self_id or "-",
            status.online,
            status.good,
        )
    await get_center().report_account(status=status, self_id=self_id)


__all__ = [
    "HeartbeatWatchdog",
    "heartbeat",
    "on_heartbeat",
    "status_from_event",
]
