"""QBot 启动入口 —— 原生 NoneBot2（替代 zhenxun-bot）。

设计与 zhenxun 的对应关系：
    zhenxun: `.venv/bin/zx run` + zhenxun/plugins 动态加载 + 106 条插件注册表
    qbot:    本文件 + `plugins/` 目录 + 无注册表（NoneBot 原生 load_plugins）

外部接线保持不变（这是迁移的关键安全垫）：
    LLBot ws-reverse → ws://127.0.0.1:8080/onebot/v11/ws
"""

from pathlib import Path
import sys

from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

import nonebot

# ---------------------------------------------------------------------------
# vendored 库：`_lingchu_bot_contracts`
#
# lingchu-bot 的 pyproject 用 uv_build 把它作为**第二个顶层模块**打进 wheel：
#     [tool.uv.build-backend]
#     module-name = ["nonebot_plugin_lingchu_bot", "_lingchu_bot_contracts"]
#     module-root = "src/plugins"
# 所以 zhenxun 那边是「装 wheel」才拥有它（site-packages 里是个裸目录）。
#
# 本项目以**源码目录**形式加载 lingchu（plugins/），wheel 机制不适用，
# 因此把仓库里同一份 contracts 模块放在项目根并显式加入 sys.path：
#   - 不污染 venv（`uv sync` 不会碰它，因为它不是 uv 管理的包）
#   - 依赖关系在代码里可见，而不是靠隐式路径
#   - NoneBot 的 `load_plugins` 会跳过以 `_` 开头的包，不会被误当插件加载
#
# 升级 lingchu 时务必同步更新 `_lingchu_bot_contracts/`（见项目根 README/计划文档）。
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 初始化（自动读 .env / .env.{ENVIRONMENT}，默认 dev → .env.dev）
nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

# 加载 plugins/ 下所有插件（每个顶层包 = 一个插件）
loaded = nonebot.load_plugins("plugins")
nonebot.logger.info(f"QBot 已加载 {len(loaded)} 个插件")

if __name__ == "__main__":
    nonebot.run()
