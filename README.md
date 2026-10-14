# qbot

QBot —— 原生 NoneBot2 宿主：**12 个插件以 git 子模块管理**，OneBot V11 接入 QQ 群（LLBot）。

> 源自 zhenxun_bot 的重写宿主（2026-09 起割接）。三条硬规矩：
> ① 插件一律 `vendor/<repo>` 子模块引入并**钉定 SHA**（升级 = 改指针 + 父仓提交推送，可追溯、可回滚）；
> ② 依赖全部 `==` 锁定（迁移目标 = 行为与迁移前完全一致，不接受版本漂移）；
> ③ 配置键按插件前缀分组（`WAIFU_*` / `FANQIE_*` / `LINGCHU_*` / `LLBOT_ALERT_*` / `PIXIV_*`）。

## 功能

- **子模块化插件管理**：`vendor/<repo>` + `[tool.nonebot] plugin_dirs`，宿主仓库记录每个插件的钉定提交
- **依赖全量锁定**：`pyproject.toml` 里 `==` 钉死版本，`uv.lock` 锁解析
- **systemd 托管**：`qbot.service` 跑 `.venv/bin/python bot.py`，日志进 journald
- **配置分层**：宿主级 `.env`（`ENVIRONMENT` / `DRIVER` / `HOST` / `PORT` / `COMMAND_START` /
  `SUPERUSERS` / `SYSTEM_PROXY` / `ALEMBIC_STARTUP_CHECK`），插件级 `.env.dev`
- **显式加载**：`bot.py` 调用 `nonebot.load_from_toml("pyproject.toml")`
  （`plugin_dirs` **不会**被 `nonebot.init()` 自动应用），并在开头 `chdir` 到项目根
  （模块名由「文件路径相对 cwd」推导）

## 插件清单

| 子模块 | 作用 | 状态 |
|---|---|---|
| `vendor/nonebot-plugin-waifu` | 今日老婆 + 群关系图（Chromium 出图） | 启用 |
| `vendor/nonebot-plugin-fanqie-verify` | 番茄读书入群验证（书评截图 OCR / 视觉判定） | 启用 |
| `vendor/lingchu-bot` | 群管理（命令体系 / WebUI / 消息存储） | 启用 |
| `vendor/nonebot-plugin-llbot-alert` | LLBot 心跳与连接告警（SMTP 邮件 + 恢复通知） | 启用 |
| `vendor/nonebot-plugin-info` | 功能菜单（读各插件 `__plugin_meta__.extra`） | 启用 |
| `vendor/nonebot-plugin-lottery` | 抽奖（禁言小助手，超时自动解禁） | 启用 |
| `vendor/nonebot-plugin-pixiv-novel` | pixiv 小说订阅推送 | 启用 |
| `vendor/nonebot-plugin-ciyuan-image` | 次元图 | 启用 |
| `vendor/nonebot-plugin-merge-forward` | 合并转发工具库（供其他插件 import） | 启用 |
| `vendor/nonebot-plugin-message-reaction` | 消息表态工具库（供其他插件 import） | 启用 |
| `vendor/nonebot-plugin-parser-lite` | 多平台链接解析（**第三方**，MIT） | 启用 |
| `vendor/nonebot-plugin-auto-unmute-superuser` | 超管自动解禁 | **停用**（`plugin_dirs` 里注释掉；原因见 pyproject 注释） |

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

`.env` 与 `.env.dev` **都不随仓库分发**（含密钥），部署时单独维护。

## 依赖与安装

- 运行环境：Python **3.13**（`>=3.13,<3.14`）；依赖由 [uv](https://docs.astral.sh/uv/) 管理
- 核心依赖：`nonebot2[fastapi,httpx,websockets]==2.5.0`、`nonebot-adapter-onebot==2.4.6`
- 插件侧宿主依赖（全部 `==` 锁定）：`nonebot-plugin-htmlrender==0.6.7` +
  `playwright==1.57.0`（配 `chromium-1200`）、`nonebot-plugin-orm[aiosqlite]==0.8.3`、
  `nonebot-plugin-localstore==0.7.4`、`nonebot-plugin-apscheduler==0.5.0`、`nonebot-plugin-alconna==0.62.0` …
- 部署（服务器，以私有 SSH 部署密钥拉取）：

```bash
git clone git@github.com:xinvxueyuan/qbot.git /path/to/qbot && cd /path/to/qbot
git submodule update --init --recursive
uv sync --frozen                 # 依赖按 pyproject + uv.lock 全量锁定
# 配置：宿主级写 .env，插件级写 .env.dev（都不入库）
systemctl restart qbot.service
```

## 测试与门禁

```bash
uv run ruff check .
```

（本仓是宿主骨架，暂无自动化测试；插件各自的测试与门禁见各插件仓库。）

## 许可

本仓库（私有）**未附加**开源许可证，默认**保留所有权利**（All rights reserved）。
