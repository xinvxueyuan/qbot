"""OneBot V11 合并转发核心工具（无 alconna 依赖）。

移植自 zhenxun_bot：
- MessageUtils.custom_forward_msg: node 构造
- MessageUtils.template2forward: 模板转 node（简化版）
- broadcast._broadcast_forward: send_group_forward_msg 发送
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAlias

from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment

if TYPE_CHECKING:
    from collections.abc import Iterable

# 单个节点内容：V11 的 content 字段（str = CQ 码 / 分段字典列表）
NodeContent: TypeAlias = str | Message | MessageSegment | list[Any] | dict
# 构造好的 V11 node 字典
V11Node: TypeAlias = dict[str, Any]

__all__ = [
    "build_node",
    "build_nodes",
    "send_forward",
    "send_group_forward_msg",
    "to_v11_content",
]


def to_v11_content(content: NodeContent) -> str | list[dict]:
    """把任意常见消息形态归一化为 V11 node 的 content 字段。

    Args:
        content: str（CQ 码）/ Message / MessageSegment / dict / dict 列表。

    Returns:
        content 字段值：str 原样返回；Message/MessageSegment/dict 转分段字典列表。
    """
    if isinstance(content, str):
        return content
    if isinstance(content, Message):
        return [seg_to_dict(seg) for seg in content]
    if isinstance(content, MessageSegment):
        return [seg_to_dict(content)]
    if isinstance(content, list):
        return [seg if isinstance(seg, dict) else seg_to_dict(seg) for seg in content]
    if isinstance(content, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
        return [content]
    msg = f"不支持的节点内容类型: {type(content).__name__}"
    raise TypeError(msg)


def seg_to_dict(seg: MessageSegment) -> dict:
    """MessageSegment 转 V11 分段字典（``{"type", "data"}``，剔除 None 默认字段）。"""
    data = {k: v for k, v in seg.data.items() if v is not None}
    return {"type": seg.type, "data": data}


def build_node(
    content: NodeContent,
    uin: str | int,
    name: str,
) -> V11Node:
    """构造单个合并转发节点（V11 node 字典）。

    Args:
        content: 节点内容，见 :func:`to_v11_content`。
        uin: 发送者 QQ 号。
        name: 发送者昵称。

    Returns:
        V11 node 字典: ``{"type": "node", "data": {"user_id", "nickname", "content"}}``
    """
    return {
        "type": "node",
        "data": {
            "user_id": str(uin),
            "nickname": name,
            "content": to_v11_content(content),
        },
    }


def build_nodes(
    messages: Iterable[NodeContent],
    uin: str | int,
    name: str,
) -> list[V11Node]:
    """批量构造合并转发节点列表。

    Args:
        messages: 每条消息的 content（同一发送者视角）。
        uin: 发送者 QQ 号。
        name: 发送者昵称。

    Returns:
        V11 node 字典列表，可直接交给 send_group_forward_msg。
    """
    return [build_node(msg, uin, name) for msg in messages]


async def send_group_forward_msg(
    bot: Bot,
    group_id: str | int,
    nodes: list[V11Node],
) -> dict[str, Any]:
    """向指定群发送合并转发消息。

    Args:
        bot: OneBot V11 Bot 实例。
        group_id: 目标群号。
        nodes: :func:`build_nodes` 构造的节点列表。

    Returns:
        协议返回的 message_id 等结果。
    """
    return await bot.send_group_forward_msg(
        group_id=int(group_id),
        messages=nodes,
    )


async def send_forward(
    bot: Bot,
    group_id: str | int,
    messages: Iterable[NodeContent],
    uin: str | int,
    name: str,
) -> dict[str, Any]:
    """一步完成：构造节点并发送合并转发。

    Args:
        bot: OneBot V11 Bot 实例。
        group_id: 目标群号。
        messages: 每条消息的 content（同一发送者视角）。
        uin: 发送者 QQ 号。
        name: 发送者昵称。

    Returns:
        协议返回的 message_id 等结果。
    """
    nodes = build_nodes(messages, uin, name)
    return await send_group_forward_msg(bot, group_id, nodes)
