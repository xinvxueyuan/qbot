"""超管自动解禁插件主模块。

监听 OneBot V11 群禁言事件：当 NoneBot 全局 ``SUPERUSERS`` 中的用户在
启用范围内被禁言时，自动调用 ``set_group_ban(duration=0)`` 解禁。

**双通道保障**：
    1. **事件驱动**（即时）：监听 ``GroupBanNoticeEvent``，禁言发生瞬间解禁。
    2. **周期轮询**（兜底）：apscheduler 定时任务周期性调用
       ``get_group_member_list``，发现保护对象处于禁言状态（遗漏事件、
       bot 掉线期间被禁言等场景）即恢复。

**权限感知（v0.2）**：QQ 协议规定管理员无法禁言/解禁同为管理员或群主的
用户。每次禁言事件落库记录 operator（``storage.record_ban_event``），
解禁前查询最近 operator 的角色：若操作者是**群主**（owner），说明这是
群主主动决定（且 bot 通常无权操作该目标），**静默跳过**不再空转尝试；
其他来源（bot 自身 API 如 poke 惩罚、管理员禁言普通成员）照常解禁。
事件遗漏导致 DB 无记录时，按目标角色兜底判断（目标为 admin/owner 且
bot 非 owner 则跳过）。

设计动机（操作后恢复保护）：
    lingchu-bot 的 protect_member 是**操作前白名单拦截**，只挡人工命令；
    bot 自身 API 调用（如 poke 戳一戳插件的惩罚逻辑）直接
    ``set_group_ban``，白名单拦不住。本插件是**操作后恢复**，两者互补。

注意：
    - ``block=False``：OCR 插件的 ``on_group_ban`` 同样监听本事件用于
      验证会话禁言状态同步，不能被拦截。
    - 超管判定使用 NoneBot 全局 ``SUPERUSERS``（非任何插件私有配置）。
    - 轮询与事件驱动对同一禁言可能各解禁一次：``set_group_ban(duration=0)``
      幂等，无副作用。
"""

from __future__ import annotations

from time import time
from typing import TYPE_CHECKING, Any

from nonebot import get_bots, get_driver, logger, on_notice, require
from nonebot.adapters.onebot.v11 import Bot, GroupBanNoticeEvent
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

from .config import plugin_config
from .storage import latest_operator, prune_events, record_ban_event

if TYPE_CHECKING:
    from collections.abc import Mapping

__plugin_meta__ = PluginMetadata(
    name="超管自动解禁",
    description="超级用户在群内被禁言时自动解禁（事件驱动 + 周期轮询兜底）",
    usage="自动运行，无需指令。被禁言的超级用户会自动解除禁言。",
    type="application",
    homepage="",
    supported_adapters={"nonebot.adapters.onebot.v11"},
    extra={
        "author": "xinvxueyuan",
        "priority": 1,
        "startup": False,
        "shutdown": False,
    },
)

driver = get_driver()

ban_notice = on_notice(priority=1, block=False)

_first_round_done: dict[str, bool] = {"done": False}


@ban_notice.handle()
async def auto_unmute_superuser(
    bot: Bot,
    event: GroupBanNoticeEvent,
) -> None:
    """超级用户在启用范围内被禁言时自动解禁。"""
    if event.sub_type != "ban":
        return
    if not _is_protected_user(str(event.user_id)):
        return
    if not _is_monitored_group(event.group_id):
        return
    # 事件落库：记录禁言操作者，供解禁决策查询。
    record_ban_event(
        group_id=event.group_id,
        user_id=event.user_id,
        operator_id=event.operator_id,
        duration=event.duration,
        banned_at=int(time()),
    )
    if await _should_skip_unmute(bot, event.group_id, event.user_id):
        return
    await _unmute(bot, event.group_id, event.user_id, source="事件驱动")


def _is_protected_user(user_id: str) -> bool:
    """是否为 NoneBot 全局超级用户。"""
    return user_id in driver.config.superusers


def _is_monitored_group(group_id: int) -> bool:
    """是否在启用范围内（配置为空 = 全部群）。"""
    groups = plugin_config.superuser_unmute_groups
    return not groups or group_id in groups


async def _should_skip_unmute(bot: Bot, group_id: int, user_id: int) -> bool:
    """判断是否应跳过自动解禁（权限不足 / 群主主动禁言）。

    优先级：
    1. 事件库有记录 → 查 operator 角色：群主（owner）→ 跳过；
       其他角色 → 可解禁。
    2. 事件库无记录（事件遗漏）→ 目标角色为 admin/owner 且 bot 非
       owner → 跳过（bot 无权限）；否则尝试解禁。

    返回 True 表示应跳过（静默，不尝试、不通知）。
    """
    operator_id = latest_operator(group_id=group_id, user_id=user_id)
    if operator_id is not None:
        operator_role = await _member_role(bot, group_id, operator_id)
        if operator_role == "owner":
            logger.info(
                "超级用户 {} 在群 {} 被群主禁言，尊重群主决定，跳过自动解禁",
                user_id,
                group_id,
            )
            return True
        return False

    # 事件遗漏兜底：按目标角色判断。
    target_role = await _member_role(bot, group_id, user_id)
    if target_role not in ("admin", "owner"):
        return False
    bot_role = await _member_role(bot, group_id, int(bot.self_id))
    if bot_role == "owner":
        return False
    logger.info(
        "超级用户 {} 在群 {} 被禁言但目标为 {}，bot 角色为 {}，无权限解禁，跳过",
        user_id,
        group_id,
        target_role,
        bot_role,
    )
    return True


async def _member_role(bot: Bot, group_id: int, user_id: int) -> str | None:
    """查询成员角色（owner/admin/member）；失败返回 None。"""
    try:
        info = await bot.get_group_member_info(
            group_id=group_id,
            user_id=user_id,
            no_cache=True,
        )
        role = info.get("role")
        return str(role) if role else None
    except Exception:
        logger.exception(
            "查询成员角色失败 group={} user={}",
            group_id,
            user_id,
        )
        return None


async def _unmute(
    bot: Bot,
    group_id: int,
    user_id: int,
    *,
    source: str,
) -> None:
    """解禁并记录日志；失败仅记日志不抛出。"""
    try:
        await bot.set_group_ban(
            group_id=group_id,
            user_id=user_id,
            duration=0,
        )
    except Exception:
        logger.exception(
            "自动解禁超级用户失败（{}） group={} user={}",
            source,
            group_id,
            user_id,
        )
        return
    logger.info(
        "超级用户 {} 在群 {} 被禁言，已自动解禁（{}）",
        user_id,
        group_id,
        source,
    )


def _member_is_muted(member: Mapping[str, Any]) -> bool:
    """判断成员是否处于禁言中。

    兼容不同 OneBot 实现：
    - ``shut_up`` 布尔字段（部分实现）；
    - ``shut_up_timestamp`` 禁言到期时间戳，兼容秒 / 毫秒单位。
    """
    if member.get("shut_up") is True:
        return True
    ts = member.get("shut_up_timestamp") or 0
    if not ts:
        return False
    if ts > 1e11:  # 毫秒时间戳
        ts /= 1000.0
    return ts > time()


async def _iter_scope_group_ids(bot: Bot) -> list[int]:
    """确定轮询群范围：配置列表或（空配置时）bot 所在全部群。"""
    groups = plugin_config.superuser_unmute_groups
    if groups:
        return list(groups)
    try:
        group_list = await bot.get_group_list()
        return [int(g["group_id"]) for g in group_list]
    except Exception:
        logger.exception("获取群列表失败，本轮跳过")
        return []


async def _poll_once(bot: Bot) -> None:
    """单轮轮询：检测启用群内超管是否被禁言，是则恢复。"""
    protected = set(driver.config.superusers)
    if not protected:
        return
    for group_id in await _iter_scope_group_ids(bot):
        try:
            members = await bot.get_group_member_list(group_id=group_id)
        except Exception:
            logger.exception(
                "轮询获取群 {} 成员列表失败，跳过该群",
                group_id,
            )
            continue
        for member in members:
            user_id = int(member.get("user_id") or 0)
            if str(user_id) not in protected:
                continue
            if _member_is_muted(member):
                if await _should_skip_unmute(bot, group_id, user_id):
                    continue
                await _unmute(bot, group_id, user_id, source="周期轮询")


async def _poll_and_restore() -> None:
    """轮询入口：遍历当前所有 bot 执行一轮检测。"""
    bots = get_bots()
    if not bots:
        return
    for bot in bots.values():
        if isinstance(bot, Bot):
            await _poll_once(bot)
    prune_events()
    if not _first_round_done["done"]:
        _first_round_done["done"] = True
        logger.info(
            "超管自动解禁轮询首轮完成：检查 {} 个 bot",
            len(bots),
        )


if plugin_config.superuser_unmute_poll_enabled:
    scheduler.add_job(
        _poll_and_restore,
        trigger="interval",
        seconds=plugin_config.superuser_unmute_poll_interval,
        id="auto_unmute_superuser_poll",
        replace_existing=True,
        misfire_grace_time=60,
        coalesce=True,
        max_instances=1,
    )
    logger.info(
        "超管自动解禁轮询已启用：间隔 {} 秒",
        plugin_config.superuser_unmute_poll_interval,
    )

__all__ = ["__plugin_meta__", "plugin_config"]
