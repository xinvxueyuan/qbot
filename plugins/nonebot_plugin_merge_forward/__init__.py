"""nonebot_plugin_merge_forward —— 合并群消息转发工具库。

抽取自 zhenxun_bot 的 MessageUtils / 广播模块，纯工具库形态，
不注册任何指令或事件监听，供其他插件 import 调用。

核心 API（纯 OneBot V11，无 alconna 依赖）:
    build_node / build_nodes: 构造合并转发 node 列表
    send_group_forward_msg: 发送合并转发到群
    send_forward: 一步完成构造 + 发送

alconna 增强（需安装 nonebot-plugin-alconna）:
    nonebot_plugin_merge_forward.uni.alc_forward_msg
    nonebot_plugin_merge_forward.uni.custom_nodes_to_v11_nodes
"""

from nonebot.plugin import PluginMetadata

from .forward import (
    build_node,
    build_nodes,
    send_forward,
    send_group_forward_msg,
    to_v11_content,
)

__plugin_meta__ = PluginMetadata(
    name="合并转发工具库",
    description=(
        "合并群消息转发工具库（抽取自 zhenxun_bot）："
        "提供 OneBot V11 合并转发 node 构造与发送 API，供其他插件集成"
    ),
    usage="作为工具库被其他插件 import 调用，不提供任何指令",
    type="library",
    homepage="https://github.com/xinvxueyuan/nonebot-plugin-merge-forward",
)

__all__ = [
    "build_node",
    "build_nodes",
    "send_forward",
    "send_group_forward_msg",
    "to_v11_content",
]
