"""告警状态机：状态变化时发送告警 / 恢复邮件。

两类异常分别上报：

- **服务异常**（``AlertKind.SERVICE_DOWN``）：由 OneBot 连接断开触发；
- **账号异常**（``AlertKind.ACCOUNT_OFFLINE``）：由 ``/get_status`` 显示
  ``online``/``good`` 为假触发。

同一对象的同类异常在冷却期内只发一封，持续异常超过冷却期后重发提醒，
恢复时补发恢复通知（可关闭）。

"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from nonebot import logger

from .mailer import send_alert_mail
from .models import AlertKind, AlertState, BotStatus

if TYPE_CHECKING:
    from .config import Config

Sender = Callable[..., Awaitable[bool]]


class AlertCenter:
    """按监控对象维护状态并在变化时发送邮件告警。"""

    def __init__(self, config: Config, sender: Sender | None = None) -> None:
        """初始化告警中心。

        Args:
            config: 插件配置。
            sender: 邮件发送函数（便于测试注入）；默认使用真实 SMTP 发送。

        """
        self._config = config
        self._send: Sender = sender or send_alert_mail
        self._states: dict[str, AlertState] = {}

    @property
    def states(self) -> dict[str, AlertState]:
        """当前各监控对象的状态快照。"""
        return self._states

    def state_of(self, key: str) -> AlertState:
        """返回某监控对象的状态（不存在时创建）。"""
        return self._states.setdefault(key, AlertState())

    async def report_service(
        self,
        *,
        self_id: str,
        healthy: bool,
        reason: str = "",
    ) -> bool:
        """上报 LLBot 服务状态（OneBot 连接是否正常）。"""
        return await self._report(
            key=f"service:{self_id}",
            kind=AlertKind.SERVICE_DOWN,
            healthy=healthy,
            reason=reason,
            target=self_id,
        )

    async def report_account(
        self,
        *,
        status: BotStatus,
        self_id: str = "",
    ) -> bool:
        """上报 LLBot 账号状态（``/get_status`` 的结果）。"""
        return await self._report(
            key="account",
            kind=AlertKind.ACCOUNT_OFFLINE,
            healthy=status.healthy,
            reason=status.reason,
            target=self_id,
        )

    async def _report(
        self,
        *,
        key: str,
        kind: AlertKind,
        healthy: bool,
        reason: str,
        target: str,
    ) -> bool:
        """核心状态流转：必要时发送邮件，返回是否发送成功。"""
        state = self.state_of(key)
        now = datetime.now(UTC)
        changed = state.healthy != healthy
        state.healthy = healthy

        if healthy:
            if state.alerting:
                state.alerting = False
                state.last_reason = ""
                if self._config.llbot_alert_notify_recovery:
                    return await self._send_recovery(kind=kind, target=target, now=now)
                logger.info("{} 已恢复正常（未发送恢复通知）: {}", kind.label, target)
            return False

        # 异常：状态刚变化，或已超过冷却期需要重发提醒。
        if not changed and state.alerting and not self._should_resend(state, now):
            logger.debug("{} 仍处于异常，冷却期内不再重复告警: {}", kind.label, target)
            return False

        state.alerting = True
        state.last_reason = reason
        state.last_alert_at = now
        return await self._send_alert(
            kind=kind, target=target, reason=reason, now=now, repeated=not changed
        )

    def _should_resend(self, state: AlertState, now: datetime) -> bool:
        """持续异常时是否应重发提醒。

        冷却期 <= 0 表示只在状态变化（异常/恢复）时发送；否则距上次告警
        达到冷却期后重发一封。

        """
        cooldown = self._config.llbot_alert_cooldown
        if cooldown <= 0:
            return False
        if state.last_alert_at is None:
            return True
        return (now - state.last_alert_at).total_seconds() >= cooldown

    async def _send_alert(
        self,
        *,
        kind: AlertKind,
        target: str,
        reason: str,
        now: datetime,
        repeated: bool,
    ) -> bool:
        """发送异常告警邮件。"""
        service = self._config.llbot_alert_service_name
        prefix = "持续异常" if repeated else "告警"
        subject = f"【{service} {prefix}】{kind.label}"
        body = "\n".join([
            f"{service} 出现{kind.label}。",
            "",
            f"故障类型：{kind.label}",
            f"故障说明：{kind.detail}",
            f"账号/服务：{target or '当前 LLBot'}",
            f"异常原因：{reason or '（接口未提供原因）'}",
            f"检测时间：{now.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
            "",
            "本邮件由 llbot-alert 插件自动发送。",
        ])
        logger.warning("[{}] {}：{}", prefix, kind.label, target or "-")
        return await self._send(self._config, subject=subject, body=body)

    async def _send_recovery(
        self,
        *,
        kind: AlertKind,
        target: str,
        now: datetime,
    ) -> bool:
        """发送恢复通知邮件。"""
        service = self._config.llbot_alert_service_name
        subject = f"【{service} 恢复】{kind.label}已恢复"
        body = "\n".join([
            f"{service} 的{kind.label}已恢复。",
            "",
            f"故障类型：{kind.label}",
            f"账号/服务：{target or '当前 LLBot'}",
            f"恢复时间：{now.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
            "",
            "本邮件由 llbot-alert 插件自动发送。",
        ])
        logger.info("[恢复] {}：{}", kind.label, target or "-")
        return await self._send(self._config, subject=subject, body=body)
