"""QBot 启动入口 —— 原生 NoneBot2（替代 zhenxun-bot）。

设计与 zhenxun 的对应关系：
    zhenxun: `.venv/bin/zx run` + zhenxun/plugins 动态加载 + 106 条插件注册表
    qbot:    本文件 + `[tool.nonebot] plugin_dirs` + 无注册表（NoneBot 原生加载）

插件来源（2026-09-29 起改为 git 子模块，见 `.gitmodules` 与 `vendor/`）：
    vendor/<仓库>/<src 路径>/<插件包>   ← 每个插件一个独立仓库，钉定提交可追溯

外部接线保持不变（这是迁移的关键安全垫）：
    LLBot ws-reverse → ws://127.0.0.1:8080/onebot/v11/ws
"""

from pathlib import Path
import os
import sys

from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

import nonebot

# ---------------------------------------------------------------------------
# 工作目录固定到项目根
#
# 两个原因，都必须在 `nonebot.init()` 之前完成：
#   1. NoneBot 读 `.env` / `.env.dev` 用的是**相对路径**；
#   2. `plugin_dirs` 里的路径是相对的，且 NoneBot 用
#      `path_to_module_name()`（相对 cwd 转点号）推导插件模块名 ——
#      cwd 不对会导致插件路径无法解析。
# systemd 已设 WorkingDirectory，这里再兜一层，避免手工运行时踩坑。
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(_PROJECT_ROOT)

# ---------------------------------------------------------------------------
# lingchu 的兄弟顶层模块：`_lingchu_bot_contracts`
#
# lingchu-bot 的 pyproject 用 uv_build 把它作为**第二个顶层模块**打进 wheel：
#     [tool.uv.build-backend]
#     module-name = ["nonebot_plugin_lingchu_bot", "_lingchu_bot_contracts"]
#     module-root = "src/plugins"
# 所以 zhenxun 那边是「装 wheel」才拥有它（site-packages 里是个裸目录）。
#
# 本项目以源码形式加载，wheel 机制不适用，因此把子模块里的
# `vendor/lingchu-bot/src/plugins` 加入 sys.path —— 该目录同时含
# `_lingchu_bot_contracts` 与 `nonebot_plugin_lingchu_bot`，
# lingchu 内部 `from _lingchu_bot_contracts import ...` 即可解析。
#
# 该模块现由子模块提供，项目根不再保留副本（避免两份内容不同步）。
# NoneBot 的目录扫描会跳过 `_` 开头的包，所以它不会被误当插件。
# ---------------------------------------------------------------------------
_LINGCHU_SRC = _PROJECT_ROOT / "vendor" / "lingchu-bot" / "src" / "plugins"
if _LINGCHU_SRC.is_dir() and str(_LINGCHU_SRC) not in sys.path:
    sys.path.append(str(_LINGCHU_SRC))

# ---------------------------------------------------------------------------
# 表态库：`nonebot_plugin_message_reaction`
#
# pixiv 插件用 `from nonebot_plugin_message_reaction import with_reaction` 接表态，
# 但 NoneBot 把插件导入成 `vendor.<仓库>.src.plugins.<包>` 这种长名 ——
# **裸包名不在 sys.path 上**，直接 import 会失败。
# 后果不是报错而更隐蔽：pixiv 插件里那次 import 有降级替身，
# 于是表态功能会**静默消失**（卡片照发、表情永远没有），日志里只有一行 info。
#
# 所以把这个目录也挂上 sys.path（与上面 lingchu 同一套办法）。
# 该目录里只有表态库一个包（无 `_` 开头的兄弟模块），NoneBot 照常按 plugin_dirs 加载它。
# ---------------------------------------------------------------------------
_REACTION_SRC = _PROJECT_ROOT / "vendor" / "nonebot-plugin-message-reaction" / "src" / "plugins"
if _REACTION_SRC.is_dir() and str(_REACTION_SRC) not in sys.path:
    sys.path.append(str(_REACTION_SRC))

# 初始化（自动读 .env / .env.{ENVIRONMENT}，默认 dev → .env.dev）
nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

# ---------------------------------------------------------------------------
# 加载插件
#
# `plugin_dirs` **不会**被 `nonebot.init()` 自动应用，必须显式调用
# `load_from_toml()`（实测确认，见 nonebot/plugin/load.py:load_from_toml）。
# 插件清单与路径维护在 pyproject.toml 的 `[tool.nonebot]` 里。
# ---------------------------------------------------------------------------
loaded = nonebot.load_from_toml(str(_PROJECT_ROOT / "pyproject.toml"))
nonebot.logger.info(f"QBot 已加载 {len(loaded)} 个插件")

if __name__ == "__main__":
    nonebot.run()
