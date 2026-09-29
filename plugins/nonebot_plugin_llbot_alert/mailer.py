"""通过 SMTP 发送告警邮件。

按共享密钥库（``env.toml``）记录的用法：``smtplib.SMTP_SSL(host, port)``
后 ``login(user, pass)``；发件人须用受 SPF 授权的域名地址。凭据由部署侧的
环境变量提供，不写死在代码里。

"""

from __future__ import annotations

import asyncio
from email.message import EmailMessage
from email.utils import formataddr
import smtplib
from typing import TYPE_CHECKING

from nonebot import logger

if TYPE_CHECKING:
    from .config import Config

#: 等待发送线程结束的额外宽限（smtplib 自身超时之外）。
_SEND_GRACE = 5.0


def resolve_recipients(config: Config) -> list[str]:
    """返回告警邮件收件人列表（已排序，便于测试与日志复现）。"""
    return sorted(address for address in config.llbot_alert_to if address.strip())


def build_message(
    config: Config,
    *,
    recipients: list[str],
    subject: str,
    body: str,
) -> EmailMessage:
    """构造告警邮件。

    Args:
        config: 插件配置（发件人信息）。
        recipients: 收件人列表。
        subject: 邮件主题。
        body: 邮件正文。

    Returns:
        组装好的邮件对象。

    """
    sender = config.llbot_alert_mail_from or config.llbot_alert_smtp_user
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((config.llbot_alert_mail_from_name, sender))
    message["To"] = ", ".join(recipients)
    message.set_content(body)
    return message


def _send_sync(
    config: Config,
    message: EmailMessage,
    recipients: list[str],
    timeout: float,
) -> None:
    """同步发送邮件（由线程池调用）。"""
    host = config.llbot_alert_smtp_host
    port = config.llbot_alert_smtp_port
    server: smtplib.SMTP
    if config.llbot_alert_smtp_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=timeout)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
    try:
        if config.llbot_alert_smtp_user:
            server.login(config.llbot_alert_smtp_user, config.llbot_alert_smtp_pass)
        server.send_message(
            message,
            from_addr=config.llbot_alert_mail_from or config.llbot_alert_smtp_user,
            to_addrs=recipients,
        )
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:  # pragma: no cover - 关闭失败无需处理
            server.close()


async def send_alert_mail(config: Config, *, subject: str, body: str) -> bool:
    """异步发送告警邮件。

    未配置收件人或 SMTP 服务器时跳过（记录告警日志）；发送失败不抛出异常，
    避免影响其他事件处理。

    Args:
        config: 插件配置。
        subject: 邮件主题。
        body: 邮件正文。

    Returns:
        是否发送成功。

    """
    recipients = resolve_recipients(config)
    if not recipients:
        logger.warning("未配置告警收件人（LLBOT_ALERT_TO），跳过邮件发送")
        return False
    if not config.llbot_alert_smtp_host:
        logger.warning("未配置 SMTP 服务器（LLBOT_ALERT_SMTP_HOST），跳过邮件发送")
        return False
    message = build_message(
        config,
        recipients=recipients,
        subject=subject,
        body=body,
    )
    timeout = max(1.0, config.llbot_alert_smtp_timeout)
    try:
        await asyncio.wait_for(
            asyncio.to_thread(_send_sync, config, message, recipients, timeout),
            timeout=timeout + _SEND_GRACE,
        )
    except TimeoutError:
        logger.warning(
            "告警邮件发送超时（>{}s），已放弃本次发送", timeout + _SEND_GRACE
        )
        return False
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning("告警邮件发送失败: {}", exc)
        return False
    logger.info("告警邮件已发送: {} → {}", subject, ", ".join(recipients))
    return True
