"""次元图插件：栗次元 (t.alcy.cc) 随机图片。

命令:
    次元图 <子命令> [张数]

子命令为分类标题（如"二次元"/"原神"/"萌版横图"），也支持 slug（如 ycy/ys）。
张数省略默认 1；超过 3 张时以合并转发形式发送（集成 nonebot-plugin-merge-forward）。
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from nonebot import on_command, require
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    Message,
    MessageEvent,
    MessageSegment,
)
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata

# 跨插件访问合并转发工具库（zhenxun 插件机制下需 require 加载为子包）
_mf = require("nonebot_plugin_merge_forward")
build_nodes = _mf.build_nodes
send_group_forward_msg = _mf.send_group_forward_msg

from .api import (
    MAX_COUNT,
    category_list_text,
    fetch_images,
    resolve_category,
)
from .render import render_category_list

__plugin_meta__ = PluginMetadata(
    name="次元图",
    description=(
        "栗次元 (t.alcy.cc) 随机图片：次元图 <分类> [张数]，超过 3 张自动合并转发"
    ),
    usage="次元图 二次元\n次元图 原神 30\n发送「次元图」查看全部分类",
    type="application",
    homepage="https://github.com/xinvxueyuan/nonebot-plugin-ciyuan-image",
)

matcher = on_command("次元图", aliases={"次元图"}, priority=10, block=True)

# 直接发图上限（含）；超过走合并转发
DIRECT_SEND_LIMIT = 3


@matcher.handle()
async def handle(
    bot: Bot,
    event: MessageEvent,
    cmd_arg: Message = CommandArg(),
) -> None:
    """处理次元图命令。

    Args:
        bot: OneBot V11 Bot 实例。
        event: 消息事件。
        cmd_arg: 命令后的参数（不含"次元图"本身）。
    """
    group_id: int | None = (
        event.group_id if isinstance(event, GroupMessageEvent) else None
    )
    user_id = event.user_id
    plain = cmd_arg.extract_plain_text().strip()
    parts = re.split(r"[\s,，、]+", plain)
    parts = [p for p in parts if p]

    if not parts:
        await send_category_list(bot, group_id, user_id)
        await matcher.finish()
    if len(parts) > 2:
        await matcher.finish("参数过多：次元图 <分类> [张数]")

    cat = resolve_category(parts[0])
    if cat is None:
        await matcher.finish(f"未知分类「{parts[0]}」，可用：\n{category_list_text()}")

    count = 1
    if len(parts) == 2:
        if not parts[1].isdigit():
            await matcher.finish(f"张数需为数字：次元图 {cat.title} <张数>")
        count = int(parts[1])
        if count < 1:
            await matcher.finish("张数需 ≥ 1")
        if count > MAX_COUNT:
            await matcher.finish(f"张数最多 {MAX_COUNT}")

    try:
        urls = await fetch_images(cat, count)
    except httpx.HTTPError as e:
        logger.warning(f"[次元图] 拉取失败: {type(e).__name__}: {e}")
        await matcher.finish("拉取图片失败，稍后再试~ (网络错误)")
    except ValueError as e:
        logger.warning(f"[次元图] 接口异常: {type(e).__name__}: {e}")
        await matcher.finish(f"拉取图片失败：{e}")

    if not urls:
        await matcher.finish("没有拿到图片，换个分类试试~")

    if count <= DIRECT_SEND_LIMIT:
        await send_direct(bot, group_id, user_id, urls)
        await matcher.finish()
    await send_forward_msg(bot, group_id, user_id, urls, cat)


async def send_category_list(
    bot: Bot,
    group_id: int | None,
    user_id: int,
) -> None:
    """发送分类列表（htmlkit 渲染图片优先，未装则回退纯文本）。

    Args:
        bot: OneBot V11 Bot 实例。
        group_id: 群号，私聊为 None。
        user_id: 私聊目标 QQ。
    """
    png = await render_category_list()
    if png is not None:
        seg = MessageSegment.image(png)
    else:
        seg = MessageSegment.text(category_list_text())
    if group_id is not None:
        await bot.send_group_msg(group_id=group_id, message=Message(seg))
    else:
        await bot.send_private_msg(user_id=user_id, message=Message(seg))


async def send_direct(
    bot: Bot,
    group_id: int | None,
    user_id: int,
    urls: list[str],
) -> None:
    """直接发送图片（≤ 3 张）。

    Args:
        bot: OneBot V11 Bot 实例。
        group_id: 群号，私聊为 None。
        user_id: 私聊目标 QQ。
        urls: 图片链接列表。
    """
    for url in urls:
        seg = MessageSegment.image(url)
        if group_id is not None:
            await bot.send_group_msg(group_id=group_id, message=Message(seg))
        else:
            await bot.send_private_msg(user_id=user_id, message=Message(seg))


async def send_forward_msg(
    bot: Bot,
    group_id: int | None,
    user_id: int,
    urls: list[str],
    cat: Any,
) -> None:
    """合并转发发送（> 3 张）。

    Args:
        bot: OneBot V11 Bot 实例。
        group_id: 群号，私聊为 None。
        user_id: 私聊目标 QQ。
        urls: 图片链接列表。
        cat: 分类对象。
    """
    if group_id is None:
        # 私聊无合并转发（OneBot V11 私聊一般不支持），逐张发送
        for url in urls:
            await bot.send_private_msg(
                user_id=user_id, message=Message(MessageSegment.image(url))
            )
        return
    nodes = build_nodes(
        [MessageSegment.image(url) for url in urls],
        uin=bot.self_id,
        name=f"次元图·{cat.title}",
    )
    await send_group_forward_msg(bot, group_id, nodes)
