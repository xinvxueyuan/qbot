"""llbot-alert：LLBot 状态告警插件（纯后端邮件通知）。

监控两类互相独立的故障并发送邮件告警：

- **服务异常**：``on_bot_disconnect`` —— OneBot 连接断开（LLBot 进程崩溃、
  网络中断等）；另有心跳静默守护，可发现「连接仍在但心跳停止」的假死；
- **账号异常**：OneBot 心跳事件（``meta_event/heartbeat``）的
  ``status.online`` / ``status.good`` —— 账号被踢下线、登录失效或被冻结。
  心跳持续到达，无需轮询 HTTP 接口。

状态恢复时补发恢复通知；同类异常在冷却期内不重复发送。

"""

from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="llbot-alert",
    description=(
        "LLBot 状态告警：从心跳事件抽取账号状态（status.online/good）检测账号异常，"
        "并在连接断开或心跳静默时检测服务异常，通过 SMTP 发送告警与恢复邮件"
        "（纯后端，无前端界面）"
    ),
    usage=(
        "配置 LLBOT_ALERT_* 环境变量后自动生效："
        "监听心跳检测账号状态，监听 on_bot_disconnect 与心跳静默检测服务异常。"
    ),
    type="application",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

# 导入即注册：NoneBot 钩子（连接事件 + 静默守护）与心跳事件响应器。
from . import heartbeat, hooks

__all__ = ["Config", "heartbeat", "hooks"]
