# qbot

QBot —— 原生 NoneBot2 宿主：**13 个插件以 git 子模块管理（12 个启用）**，OneBot V11 接入 QQ 群（LLBot）。

[![Python](https://img.shields.io/badge/python-3.13-blue)](pyproject.toml)

> 源自 zhenxun_bot 的重写宿主（2026-09 起割接）。三条硬规矩：
> ① 插件一律 `vendor/<repo>` 子模块引入并**钉定 SHA**（升级 = 改指针 + 父仓提交推送，可追溯、可回滚）；
> ② 依赖全部 `==` 锁定（迁移目标 = 行为与迁移前完全一致，不接受版本漂移）；
> ③ 配置键按插件前缀分组（`WAIFU_*` / `FANQIE_*` / `LINGCHU_*` / `LLBOT_ALERT_*` / `PIXIV_*`）。

## 功能特性

- **子模块化插件管理**：`vendor/<repo>` + `[tool.nonebot] plugin_dirs`，宿主仓库记录每个插件的钉定提交
- **依赖全量锁定**：`pyproject.toml` 里 `==` 钉死版本，`uv.lock` 锁解析
- **systemd 托管**：`qbot.service` 跑 `.venv/bin/python bot.py`，日志进 journald
- **配置分层**：宿主级 `.env`（`ENVIRONMENT` / `DRIVER` / `HOST` / `PORT` / `COMMAND_START` /
  `SUPERUSERS` / `SYSTEM_PROXY` / `ALEMBIC_STARTUP_CHECK`），插件级 `.env.dev`
- **显式加载**：`bot.py` 调用 `nonebot.load_from_toml("pyproject.toml")`
  （`plugin_dirs` **不会**被 `nonebot.init()` 自动应用），并在开头 `chdir` 到项目根
  （模块名由「文件路径相对 cwd」推导）

### 插件清单

下表与 `.gitmodules` **逐项对应**（顺序同 `.gitmodules`，共 13 个子模块）；「状态」以 `pyproject.toml` 的
`[tool.nonebot] plugin_dirs` 为准 —— 列在其中即为启用。

| 子模块 | 上游 | 作用 | 状态 |
|---|---|---|---|
| `vendor/nonebot-plugin-fanqie-verify` | xinvxueyuan | 番茄读书入群验证（书评截图 OCR / 视觉判定） | 启用 |
| `vendor/lingchu-bot` | xinvxueyuan | 群管理（命令体系 / WebUI / 消息存储） | 启用 |
| `vendor/nonebot-plugin-llbot-alert` | xinvxueyuan | LLBot 心跳与连接告警（SMTP 邮件 + 恢复通知） | 启用 |
| `vendor/nonebot-plugin-parser-lite` | sokoko-org（**第三方**，MIT） | 多平台链接解析 | 启用 |
| `vendor/nonebot-plugin-merge-forward` | xinvxueyuan | 合并转发工具库（供其他插件 import） | 启用 |
| `vendor/nonebot-plugin-ciyuan-image` | xinvxueyuan | 次元图 | 启用 |
| `vendor/nonebot-plugin-auto-unmute-superuser` | xinvxueyuan | 超管自动解禁 | **停用**（`plugin_dirs` 里注释掉；原因见 pyproject 注释） |
| `vendor/nonebot-plugin-pixiv-novel` | xinvxueyuan | pixiv 小说订阅推送 | 启用 |
| `vendor/nonebot-plugin-message-reaction` | xinvxueyuan | 消息表态工具库（供其他插件 import） | 启用 |
| `vendor/nonebot-plugin-lottery` | xinvxueyuan | 抽奖（禁言小助手，超时自动解禁） | 启用 |
| `vendor/nonebot-plugin-waifu` | xinvxueyuan | 今日老婆 + 群关系图（Chromium 出图） | 启用 |
| `vendor/nonebot-plugin-info` | xinvxueyuan | 功能菜单（读各插件 `__plugin_meta__.extra`） | 启用 |
| `vendor/nonebot-plugin-pixiv-illust` | xinvxueyuan | pixiv 插画 / 漫画订阅推送（多页，R18 可打码） | 启用 |
| `vendor/nonebot-plugin-checkin` | xinvxueyuan | 群签到：每日签到攒积分、连续天数加成、群内积分排行（图卡含昵称与头像） | 启用 |

子模块在父仓里记录的是**钉定提交 SHA**；`.gitmodules` 里的 `branch` 只在 `git submodule update --remote`
时生效，日常部署以父仓指针为准。`vendor/nonebot-plugin-auto-unmute-superuser` 的子模块仍在仓内（钉定版本），
恢复方式 = 取消 `plugin_dirs` 中该行的注释并重启。

## 安装

- 运行环境：Python **3.13**（`>=3.13,<3.14`）；依赖由 [uv](https://docs.astral.sh/uv/) 管理
- 核心依赖：`nonebot2[fastapi,httpx,websockets]==2.5.0`、`nonebot-adapter-onebot==2.4.6`
- 插件侧宿主依赖（全部 `==` 锁定）：`nonebot-plugin-htmlrender==0.6.7` +
  `playwright==1.57.0`（配 `chromium-1200`）、`nonebot-plugin-orm[aiosqlite]==0.8.3`、
  `nonebot-plugin-localstore==0.7.4`、`nonebot-plugin-apscheduler==0.5.0`、`nonebot-plugin-alconna==0.62.0` …

### 部署（服务器侧）

```bash
git clone https://github.com/xinvxueyuan/qbot.git /path/to/qbot && cd /path/to/qbot
git submodule update --init --recursive
uv sync --frozen                 # 依赖按 pyproject + uv.lock 全量锁定
# 配置：宿主级写 .env，插件级写 .env.dev（都不入库）
systemctl restart qbot.service
```

启动链路：`qbot.service` → `.venv/bin/python bot.py` → `chdir` 到项目根 → `nonebot.init()`
（读 `.env` / `.env.{ENVIRONMENT}`）→ `load_from_toml("pyproject.toml")` → `nonebot.run()`。

### 升级子模块

```bash
cd vendor/<repo> && git fetch && git checkout <SHA>          # 钉定提交
cd ../.. && git add vendor/<repo> && git commit && git push  # 父仓指针必须入库
systemctl restart qbot.service
```

## 配置

| 键 | 说明 |
|---|---|
| `ENVIRONMENT` | 环境名（`dev` = 读 `.env.dev`） |
| `DRIVER` | NoneBot 驱动（FastAPI） |
| `HOST` / `PORT` | 监听地址 / 端口（默认 8080） |
| `COMMAND_START` | 命令前缀（含空串 → 裸词也能触发命令） |
| `SUPERUSERS` | 宿主级超管 QQ 列表 |
| `SYSTEM_PROXY` | 出网代理（供需要访问境外的插件使用） |
| `ALEMBIC_STARTUP_CHECK` | ORM 启动迁移检查开关（**关掉时 `migrate.sync` 会 DROP 本进程无模型的表**，干跑务必隔离数据目录） |
| `.env.dev` 里的 `<插件前缀>_*` | 各插件自己的配置（`WAIFU_*` / `FANQIE_*` / `LINGCHU_*` / …），按前缀分组、由插件自读 |

`.env` 与 `.env.dev` **都不随仓库分发**（含密钥），部署时单独维护。仓内未附 `.env.example`，
键名以上表为准；插件的完整键表见各插件仓库的 README。

## 使用 / 命令

宿主本身**不注册任何命令**：`bot.py` 只做初始化与插件加载，命令全部由 `vendor/` 下的插件各自注册。
查「当前装了什么、有哪些命令」的入口是 `vendor/nonebot-plugin-info` 生成的功能菜单
（读各插件的 `__plugin_meta__.extra`）。

- **触发方式**：`COMMAND_START` 含空串，命令可用裸词触发（例：pixiv 插画插件的
  `订阅插画 <画师id>` / `退订插画 <画师id>` / `插画订阅列表`，完整命令表见该插件仓库）。
- **接入**：LLBot 以 ws-reverse 连 `ws://127.0.0.1:8080/onebot/v11/ws`（宿主 `HOST` / `PORT` 默认 8080）。

运维：

```bash
systemctl status qbot.service
systemctl restart qbot.service
journalctl -u qbot.service -f        # 插件日志要进 journald，需插件侧挂 LoguruHandler 桥
git submodule status                 # 全部子模块的实际 SHA
git -C vendor/<repo> rev-parse HEAD  # 与上一行对照，确认部署的就是期望提交
```

## 开发与测试

- 开发依赖（`[dependency-groups].dev`）：`pytest>=8.0`、`pytest-asyncio>=0.24`、`ruff>=0.6`、`pyright>=1.1`
- 代码风格：`[tool.ruff]` `line-length = 88`、`target-version = "py313"`，lint 规则
  `E` / `F` / `I` / `UP` / `B` / `PL` / `RUF`（忽略 `PLR0913`）
- 门禁（本仓当前唯一可跑的一条）：

```bash
uv run ruff check .
```

- **本仓是宿主骨架，暂无自动化测试**：仓内没有 `tests/` 目录，也没有 CI workflow；插件各自的测试与门禁见各插件仓库。
- 数据目录自检：`t23_check_datadir.py` 打印 `localstore` 的 `BASE_DATA_DIR` 与推导出的 ORM 数据目录，
  用于确认升级前后读写的是同一个库（路径不符会以退出码 1 结束）。
- 插件开发纪律（与 `AGENTS.md` 一致）：
  - 插件一律以 `vendor/<repo>` 子模块引入，URL 用 HTTPS，**钉定提交 SHA**；
  - 新增插件 = 父仓加子模块 + `[tool.nonebot] plugin_dirs` 加一行（该键不会由 `nonebot.init()` 自动生效）；
  - **不要** `pip install -e .`：`.pth` 会让 `vendor/` 下的子模块目录被当成包目录，产生假的 `already exists`；
  - 依赖变更只做加法，改完 `uv pip list` 前后 diff 只许有新增行。

## 许可证与相关仓库

### 许可证

仓库根**没有** `LICENSE` 文件，即**未声明**开源许可证，默认**保留所有权利**（All rights reserved）。
对外复用（含 fork 后分发）前请先联系作者。

### 相关仓库

| 仓库 | 关系 |
|---|---|
| [xinvxueyuan/qbot](https://github.com/xinvxueyuan/qbot) | 本仓：宿主骨架（`bot.py` + 子模块指针 + 配置） |
| [xinvxueyuan/lingchu-bot](https://github.com/xinvxueyuan/lingchu-bot) | 群管理插件；宿主额外把 `vendor/lingchu-bot/src/plugins` 挂进 `sys.path`，以解析它的兄弟顶层模块 `_lingchu_bot_contracts` |
| [xinvxueyuan/nonebot-plugin-info](https://github.com/xinvxueyuan/nonebot-plugin-info) | 功能菜单，读各插件 `__plugin_meta__.extra` |
| [xinvxueyuan/nonebot-plugin-merge-forward](https://github.com/xinvxueyuan/nonebot-plugin-merge-forward) | 合并转发工具库，被 pixiv 等插件的多页推送 import |
| [xinvxueyuan/nonebot-plugin-message-reaction](https://github.com/xinvxueyuan/nonebot-plugin-message-reaction) | 消息表态工具库，pixiv 插件用它做「处理中 / 完成」反馈 |
