"""alconna 增强：跨平台合并转发构造 + UniMessage → V11 转换（可选依赖）。

移植自 zhenxun_bot：
- MessageUtils.alc_forward_msg: CustomNode + Reference 跨平台构造
- broadcast/utils.py: uni_segment_to_v11_segment_dict /
  uni_message_to_v11_list_of_dicts / custom_nodes_to_v11_nodes

本模块仅在调用时导入 nonebot-plugin-alconna，未安装则抛出 ImportError。
"""

from __future__ import annotations

import base64
import importlib.util
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nonebot_plugin_alconna import UniMessage

__all__ = [
    "alc_forward_msg",
    "custom_nodes_to_v11_nodes",
    "uni_message_to_v11_list_of_dicts",
    "uni_segment_to_v11_segment_dict",
]

_ALCONNA_NOT_INSTALLED_MSG = (
    "使用 alconna 增强功能需要安装 nonebot-plugin-alconna："
    "pip install 'nonebot-plugin-merge-forward[alconna]'"
)


def _require_alconna() -> None:
    """确保 alconna 已安装，否则抛出带指引的 ImportError。"""
    if importlib.util.find_spec("nonebot_plugin_alconna") is None:
        raise ImportError(_ALCONNA_NOT_INSTALLED_MSG)


def alc_forward_msg(
    msg_list: list[Any],
    uin: str | int,
    name: str,
) -> UniMessage:
    """生成跨平台自定义合并消息（alconna CustomNode + Reference）。

    Args:
        msg_list: 每条消息的内容（str / Message / 分段等，alconna 可接收的形态）。
        uin: 发送者 QQ 号。
        name: 发送者昵称。

    Returns:
        UniMessage，可直接 .send() 发送（跨平台，非 V11 也兼容）。
    """
    _require_alconna()
    from nonebot_plugin_alconna import CustomNode, UniMessage
    from nonebot_plugin_alconna.uniseg import Reference

    node_list = [
        CustomNode(uid=str(uin), name=name, content=UniMessage(msg)) for msg in msg_list
    ]
    return UniMessage(Reference(nodes=node_list))


def uni_segment_to_v11_segment_dict(
    seg: Any,
    depth: int = 0,
    max_depth: int = 3,
) -> dict | list[dict] | None:
    """UniMessage 单段转 V11 分段字典（广播模块移植，深度限制防嵌套转发死循环）。

    Args:
        seg: alconna 分段对象（Text/Image/At/AtAll/Video/Reference 等）。
        depth: 当前递归深度。
        max_depth: 嵌套转发最大解析深度。

    Returns:
        V11 分段字典或字典列表；不支持的段返回 None。
    """
    import nonebot_plugin_alconna as alc
    from nonebot_plugin_alconna.uniseg import Reference
    from nonebot_plugin_alconna.uniseg.segment import CustomNode, Video

    if isinstance(seg, alc.Text):
        return {"type": "text", "data": {"text": seg.text}}
    if isinstance(seg, alc.Image):
        if getattr(seg, "url", None):
            return {"type": "image", "data": {"file": seg.url}}
        if getattr(seg, "raw", None):
            raw_data: bytes | str = seg.raw  # type: ignore[assignment]
            if isinstance(raw_data, str) and raw_data.startswith("base64://"):
                return {"type": "image", "data": {"file": raw_data}}
            if isinstance(raw_data, bytes):
                b64 = base64.b64encode(raw_data).decode()
                return {"type": "image", "data": {"file": f"base64://{b64}"}}
        if getattr(seg, "path", None):
            return {"type": "image", "data": {"file": f"file:///{seg.path}"}}
        return None
    if isinstance(seg, alc.At):
        return {"type": "at", "data": {"qq": seg.target}}
    if isinstance(seg, alc.AtAll):
        return {"type": "at", "data": {"qq": "all"}}
    if isinstance(seg, Video):
        if getattr(seg, "url", None):
            return {"type": "video", "data": {"file": seg.url}}
        if getattr(seg, "raw", None):
            raw_data: bytes | str = seg.raw  # type: ignore[assignment]
            if isinstance(raw_data, str) and raw_data.startswith("base64://"):
                return {"type": "video", "data": {"file": raw_data}}
            if isinstance(raw_data, bytes):
                b64 = base64.b64encode(raw_data).decode()
                return {"type": "video", "data": {"file": f"base64://{b64}"}}
        if getattr(seg, "path", None):
            return {"type": "video", "data": {"file": f"file:///{seg.path}"}}
        return None
    if isinstance(seg, Reference) and getattr(seg, "nodes", None):
        if depth >= max_depth:
            return {"type": "text", "data": {"text": "[嵌套转发层数过多，内容已省略]"}}
        nested: list[dict] = []
        for node in getattr(seg, "nodes", []):
            if not isinstance(node, CustomNode):
                continue
            node_content: list[dict] = []
            content = node.content
            if isinstance(content, alc.UniMessage):
                for nested_seg in content:
                    converted = uni_segment_to_v11_segment_dict(
                        nested_seg, depth + 1, max_depth
                    )
                    if isinstance(converted, list):
                        node_content.extend(converted)
                    elif converted:
                        node_content.append(converted)
            elif isinstance(content, str):
                node_content.append({"type": "text", "data": {"text": content}})
            if node_content:
                nested.append({"type": "text", "data": {"text": "\n"}})
                nested.append({
                    "type": "text",
                    "data": {"text": f"--- 来自 {node.name} ({node.uid}) ---\n"},
                })
                nested.extend(node_content)
        return nested
    return None


def uni_message_to_v11_list_of_dicts(uni_msg: Any) -> list[dict]:
    """UniMessage / str / list 转 V11 分段字典列表（广播模块移植）。

    Args:
        uni_msg: UniMessage 或 str 或分段列表。

    Returns:
        V11 分段字典列表。
    """
    _require_alconna()
    from nonebot_plugin_alconna.uniseg.segment import Video

    if isinstance(uni_msg, str):
        return [{"type": "text", "data": {"text": uni_msg}}]
    if isinstance(uni_msg, list):
        if not uni_msg:
            return []
        if all(isinstance(item, str) for item in uni_msg):
            return [{"type": "text", "data": {"text": item}} for item in uni_msg]
        result: list[dict] = []
        for item in uni_msg:
            if hasattr(item, "__iter__") and not isinstance(item, str | bytes):
                result.extend(uni_message_to_v11_list_of_dicts(item))
            elif hasattr(item, "text") and not isinstance(item, str | bytes):
                result.append({"type": "text", "data": {"text": str(item.text)}})
            elif hasattr(item, "url") and not isinstance(item, str | bytes):
                if isinstance(item, Video):
                    result.append({"type": "video", "data": {"file": str(item.url)}})
                else:
                    result.append({"type": "image", "data": {"file": str(item.url)}})
            else:
                result.append({"type": "text", "data": {"text": str(item)}})
        return result
    return [{"type": "text", "data": {"text": str(uni_msg)}}]


def custom_nodes_to_v11_nodes(custom_nodes: list[Any]) -> list[dict]:
    """Alconna CustomNode 列表转 V11 node 列表（广播模块移植）。

    Args:
        custom_nodes: CustomNode 列表（通常来自 Reference.nodes）。

    Returns:
        V11 node 字典列表，可直接交给 send_group_forward_msg。
    """
    v11_nodes: list[dict] = []
    for node in custom_nodes:
        content_list = uni_message_to_v11_list_of_dicts(node.content)
        if content_list:
            v11_nodes.append({
                "type": "node",
                "data": {
                    "user_id": str(node.uid),
                    "nickname": node.name,
                    "content": content_list,
                },
            })
    return v11_nodes
