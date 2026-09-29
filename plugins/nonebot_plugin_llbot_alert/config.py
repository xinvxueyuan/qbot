"""LLBot 状态告警插件配置。

配置项均通过环境变量（前缀 ``LLBOT_ALERT_``）注入，由 NoneBot2 的
``get_plugin_config`` 统一解析；环境变量名与字段名大小写不敏感。

SMTP 凭据不写死在代码中，部署时由 ``.env`` / ``.env.dev`` 提供。

"""

from pydantic import BaseModel, Field


class Config(BaseModel):
    """LLBot 状态告警插件配置。

    Attributes:
        llbot_alert_enabled: 是否启用告警（关闭时既不处理心跳也不监听连接事件）。
        llbot_alert_service_name: 告警文案中的服务名。
        llbot_alert_accounts: 需要监控的账号 QQ 号集合；空集合表示全部。
        llbot_alert_to: 告警邮件收件人集合。
        llbot_alert_cooldown: 同类告警的最小重发间隔（秒），防止刷邮件。
        llbot_alert_notify_recovery: 状态恢复时是否补发恢复通知。
        llbot_alert_heartbeat_timeout: 心跳静默超时（秒）：超过该时长未收到
            任何心跳即判定为服务异常（连接假死/事件通道阻塞）；``0`` 表示
            不检测静默。
        llbot_alert_check_interval: 心跳静默检查的间隔（秒）。
        llbot_alert_smtp_timeout: SMTP 连接/发送超时（秒）；超时后放弃本次
            发送，避免阻塞事件循环导致进程无法及时退出。
        llbot_alert_smtp_host: SMTP 服务器地址。
        llbot_alert_smtp_port: SMTP 端口（SSL 通常为 465）。
        llbot_alert_smtp_ssl: 是否使用 SMTP_SSL。
        llbot_alert_smtp_user: SMTP 登录用户名。
        llbot_alert_smtp_pass: SMTP 登录密码。
        llbot_alert_mail_from: 发件人地址。
        llbot_alert_mail_from_name: 发件人显示名。

    """

    llbot_alert_enabled: bool = True
    llbot_alert_service_name: str = "LLBot"
    llbot_alert_accounts: set[int] = Field(default_factory=set)
    llbot_alert_to: set[str] = Field(default_factory=set)
    llbot_alert_cooldown: int = 600
    llbot_alert_notify_recovery: bool = True
    llbot_alert_heartbeat_timeout: int = 60
    llbot_alert_check_interval: int = 15
    llbot_alert_smtp_timeout: float = 10.0
    llbot_alert_smtp_host: str = ""
    llbot_alert_smtp_port: int = 465
    llbot_alert_smtp_ssl: bool = True
    llbot_alert_smtp_user: str = ""
    llbot_alert_smtp_pass: str = ""
    llbot_alert_mail_from: str = ""
    llbot_alert_mail_from_name: str = "LLBot Alert"
