# AGENTS.md — qbot（原生 NoneBot2 QQ 机器人）

腾讯云上的生产 QQ 机器人（地址略），2026-09-29 由 zhenxun_bot 割接而来。
服务 `qbot.service`，端口 `8080`，机器人 QQ `3128682634`。旧 zhenxun 保留可回滚。

⚠️ **单实例约束**：qbot 与 zhenxun 争 8080 和同一个 QQ 号，**绝不能同时 active**
（`qbot.service` 已带 `Conflicts=zhenxun.service`）。
回滚：`systemctl stop qbot && systemctl reset-failed zhenxun && systemctl start zhenxun`

## 插件引入铁律（用户拍板，约束此后所有插件）

1. 插件**一律 git 子模块**引入：挂在 `vendor/<repo>`，URL 用 **HTTPS**。
2. 宿主配置加一行 `[tool.nonebot] plugin_dirs` 指到该插件的源码子目录。
3. **严禁**把插件源码 `scp` / 拷贝进服务器 —— 无版本可追溯、无法回滚。
4. **严禁** `pip install -e .` —— `.pth` 会让 `vendor/` 下的子模块目录被当成包目录，
   产生假的 `already exists` 报错。
5. 子模块必须**钉定提交 SHA**并记录；升级 = 改钉定的 SHA。
6. 部署后必须核实**远端 SHA == 期望值**：
   `git -C vendor/<repo> rev-parse HEAD` 与 `git submodule status` 两处一致。
7. 父仓库的子模块指针**必须 commit + push**，否则指针不入库。

## 当前 13 个子模块 / 12 个启用（均在 `vendor/`）

数字以 `.gitmodules`（13 个 `path`）与 `pyproject.toml` 的 `plugin_dirs`（12 条未注释）为准；
下表与 `.gitmodules` 逐项对应，「停用」= 子模块仍在仓内（钉定 SHA），但 `plugin_dirs` 里已注释掉、不加载。

| plugin_dirs | 子模块 | 上游 |
|---|---|---|
| `nonebot-plugin-fanqie-verify/src/plugins` | 番茄入群验证 | xinvxueyuan/nonebot-plugin-fanqie-verify |
| `lingchu-bot/src/plugins` | 群管（超管自动解禁） | xinvxueyuan/lingchu-bot |
| `nonebot-plugin-llbot-alert/src/plugins` | 掉线告警 | xinvxueyuan/nonebot-plugin-llbot-alert |
| `nonebot-plugin-parser-lite/src` | 链接解析 | sokoko-org/nonebot-plugin-parser-lite |
| `nonebot-plugin-merge-forward/src/plugins` | 合并转发 | xinvxueyuan/nonebot-plugin-merge-forward |
| `nonebot-plugin-ciyuan-image/src/plugins` | 次元图 | xinvxueyuan/nonebot-plugin-ciyuan-image |
| （停用）`nonebot-plugin-auto-unmute-superuser/src/plugins` | 超管自动解禁 | xinvxueyuan/nonebot-plugin-auto-unmute-superuser |
| `nonebot-plugin-pixiv-novel/src/plugins` | pixiv 小说订阅/被动卡片 | xinvxueyuan/nonebot-plugin-pixiv-novel |
| `nonebot-plugin-message-reaction/src/plugins` | 消息表态工具库 | xinvxueyuan/nonebot-plugin-message-reaction |
| `nonebot-plugin-lottery/src/plugins` | 抽奖（禁言小助手） | xinvxueyuan/nonebot-plugin-lottery |
| `nonebot-plugin-waifu/src/plugins` | 今日老婆 + 群关系图 | xinvxueyuan/nonebot-plugin-waifu |
| `nonebot-plugin-info/src/plugins` | 功能菜单 | xinvxueyuan/nonebot-plugin-info |
| `nonebot-plugin-pixiv-illust/src/plugins` | pixiv 插画/漫画订阅 | xinvxueyuan/nonebot-plugin-pixiv-illust |

外加基础设施插件：alconna、apscheduler、htmlkit、htmlrender、localstore、orm、uninfo、waiter。

## 配置

- 环境变量放 `.env.dev`：**只做追加式修改**，严禁整文件覆盖。
- 依赖变更只做加法；改完 `uv pip list` 前后 diff **只许有新增行**。
- `[tool.nonebot] plugin_dirs` 不会由 `nonebot.init()` 自动生效，改完要确认。

## 数据库（踩过大坑）

- 共用 ORM 库：`~/.local/share/nonebot2/nonebot_plugin_orm/db.sqlite3`（示例路径，按实际 `LOCALSTORE_DATA_DIR` 展开）。
- ⚠️ `ALEMBIC_STARTUP_CHECK=false` 时，ORM 的 `migrate.sync` 会 **DROP 掉本进程没有模型的表**。
  所以**隔离干跑必须**把 `LOCALSTORE_DATA_DIR` 指到别的目录，否则会删生产表。
- 验收必须核对**表数 / 表名**与重启前一致。
- 本机**没装 `sqlite3` CLI** → 用 `python3 -c` 读库。

## 部署流程（照这个顺序）

1. **只读**检查现状：父/子 SHA、`systemctl is-active`、ORM 表数。
2. 备份：`cp -a .env.dev ~/qbot_env.dev.bak-<TS>`（示例路径）。
3. 升子模块：`cd vendor/<repo> && git fetch && git checkout <SHA>`
   （境外网络走 `https_proxy=http://127.0.0.1:<本地代理端口>`）。
4. 只有依赖变更时才装依赖。
5. 父仓库：`git add vendor/... && git commit && git push`。
6. 重启：`systemctl restart qbot.service`。
7. 验收（**不是** `is-active` 就算过）：
   - 子模块实际 SHA == 指针 == 期望值
   - journal 里 `Traceback` / `failed to import` / `already exists` 全为 0
   - 启动行显示的是预期配置
   - ORM 表数 / 表名与重启前一致
   - `8080` 在听、`Bot <QQ> connected`
8. 回滚 = `git revert <该提交>`，或把子模块 checkout 回旧 SHA 再重启。

## 不要做的事

- 不要改应用自身的 HOST/PORT —— 「暴露端口」指的是**边缘层端口镜像**。
- 不要在服务器端对凭据做 hash 逆向 / 乱试 cookie 之类的绕路探测，缺凭据直接问用户。
- 插件日志想出现在 journal 里，需要插件侧挂 `nonebot.log.LoguruHandler` 桥。
