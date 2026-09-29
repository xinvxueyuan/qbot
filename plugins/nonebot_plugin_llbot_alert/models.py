"""告警插件的内部数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

_RETCODE_OK = 0


class AlertKind(StrEnum):
    """异常类别（对应两类不同的故障）。"""

    #: LLBot 服务异常：OneBot 连接断开（进程崩溃、网络中断等）。
    SERVICE_DOWN = "service_down"
    #: 账号异常：账号下线（被踢下线、登录失效、账号被冻结等）。
    ACCOUNT_OFFLINE = "account_offline"

    @property
    def label(self) -> str:
        """中文标签（用于邮件文案）。"""
        return {
            AlertKind.SERVICE_DOWN: "服务异常",
            AlertKind.ACCOUNT_OFFLINE: "账号异常",
        }[self]

    @property
    def detail(self) -> str:
        """故障说明（用于邮件正文）。"""
        return {
            AlertKind.SERVICE_DOWN: "OneBot 连接断开：LLBot 进程异常、崩溃或网络中断",
            AlertKind.ACCOUNT_OFFLINE: "账号已下线：账号被踢下线、登录失效或被冻结",
        }[self]


@dataclass(frozen=True, slots=True)
class BotStatus:
    """``/get_status`` 返回的账号状态。

    Attributes:
        online: 账号是否在线。
        good: 账号是否处于正常状态。
        retcode: 接口返回码（非 0 或缺失表示调用异常）。
        message: 接口返回的提示信息。
        wording: 接口返回的附加文案（通常记录离线原因）。

    """

    online: bool
    good: bool
    retcode: int | None = None
    message: str | None = None
    wording: str | None = None

    @property
    def healthy(self) -> bool:
        """账号是否健康（在线且状态正常，且接口返回码正常）。"""
        if self.retcode is not None and self.retcode != _RETCODE_OK:
            return False
        return self.online and self.good

    @property
    def reason(self) -> str:
        """异常原因的文本描述。"""
        parts = [text for text in (self.message, self.wording) if text and text.strip()]
        return " / ".join(parts)


@dataclass(slots=True)
class AlertState:
    """单个监控对象（某账号或服务）的告警状态。

    Attributes:
        healthy: 当前是否健康。
        alerting: 是否处于已告警（未恢复）状态。
        last_reason: 最近一次异常原因。
        last_alert_at: 最近一次发出异常告警的时间。
        last_recovery_at: 最近一次发出恢复通知的时间。

    """

    healthy: bool = True
    alerting: bool = False
    last_reason: str = ""
    last_alert_at: datetime | None = None
    last_recovery_at: datetime | None = None
