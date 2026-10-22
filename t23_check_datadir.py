#!/usr/bin/env python3
"""T23 — 校验 qbot 不设 LOCALSTORE_DATA_DIR 时解析到的 ORM 数据目录。

`nonebot_plugin_orm` 用 `get_plugin_data_dir()` → `_get_plugin_path(BASE_DATA_DIR, ...)`，
在未配置 `localstore_plugin_data_dir` 映射时退化为 `BASE_DATA_DIR / <plugin_id>`。
所以本脚本同时打印 BASE_DATA_DIR 与推导出的 ORM 目录，并直接读 BASE_DATA_DIR 的来源
（`localstore_data_dir` 配置 / `LOCALSTORE_DATA_DIR` 环境变量 / 默认值）。

必须与 zhenxun 用的是同一个目录，否则读不到业务数据（10 万+ 行）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 显式清掉隔离变量，模拟 systemd 启动时的干净环境
os.environ.pop("LOCALSTORE_DATA_DIR", None)

import nonebot  # noqa: E402

nonebot.init()

import nonebot_plugin_localstore as ls  # noqa: E402

BASE = ls.BASE_DATA_DIR
ORM_DIR = BASE / "nonebot_plugin_orm"
db = ORM_DIR / "db.sqlite3"

#: 与家目录相对: root 用户下即其家目录的 .local/share, 不写死服务器绝对路径
EXPECTED = Path.home() / ".local/share/nonebot2/nonebot_plugin_orm"

print(f"  BASE_DATA_DIR          : {BASE}")
print(f"  环境变量 LOCALSTORE_DATA_DIR : {os.environ.get('LOCALSTORE_DATA_DIR', '(未设置)')}")
print(f"  localstore_data_dir 配置     : {ls.plugin_config.localstore_data_dir}")
print(f"  localstore_use_cwd 配置      : {ls.plugin_config.localstore_use_cwd}")
print()
print(f"  推导出的 ORM 数据目录  : {ORM_DIR}")
print(f"  期望                   : {EXPECTED}")
print(f"  DB 文件                : {db}")
print(f"  DB 存在                : {db.is_file()}")
if db.is_file():
    print(f"  DB 大小                : {db.stat().st_size / 1024 / 1024:.1f} MB")

ok = str(ORM_DIR) == str(EXPECTED)
print()
print("  ✅ 与 zhenxun 同一个库 —— 零数据迁移" if ok else "  ❌ 路径不一致！停下排查")

sys.exit(0 if ok else 1)
