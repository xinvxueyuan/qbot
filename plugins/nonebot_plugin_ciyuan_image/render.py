"""分类列表图片渲染（基于 nonebot-plugin-htmlkit，可选依赖）。

htmlkit 未安装时返回 None，调用方回退纯文本。
"""

from __future__ import annotations

import importlib.util

from nonebot import require

from .api import CATEGORIES

HTMLKIT_AVAILABLE = importlib.util.find_spec("nonebot_plugin_htmlkit") is not None

_KIND_LABEL = {
    "json": "JSON 多图",
    "direct": "直连单图",
    "video": "视频",
}

_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body { margin:0; font-family:"Noto Sans CJK SC","Microsoft YaHei",sans-serif;
       background:#12141a; color:#e8ecf4; padding:24px; }
h1 { font-size:24px; margin:0 0 4px; color:#0f8b8d; letter-spacing:1px; }
.sub { font-size:12px; color:#8a94a6; margin-bottom:18px; }
.grid { display:grid; grid-template-columns:repeat(3,1fr); gap:9px; }
.card { background:#1c2029; border:1px solid #262c38; border-radius:9px;
        padding:10px 12px; }
.title { font-size:14px; font-weight:700; }
.slug { font-size:11px; color:#5d6a7e; margin-top:3px; }
.hint { margin-top:16px; font-size:11px; color:#5d6a7e; line-height:1.7; }
code { background:#1c2029; padding:1px 5px; border-radius:4px; color:#7fb4b5; }
</style></head><body>
<h1>✦ 次元图</h1>
<div class="sub">栗次元 t.alcy.cc 随机图片 · 共 {n} 个分类</div>
<div class="grid">
{cards}
</div>
<div class="hint">
用法：<code>次元图 &lt;分类&gt; [张数]</code><br/>
例：<code>次元图 原神</code> · <code>次元图 二次元 5</code><br/>
<code>次元图 ysmp 10</code> · 4 张及以上自动合并转发<br/>
数据来源 t.alcy.cc
</div>
</body></html>"""


def _build_html() -> str:
    """生成分类列表 HTML。"""
    cards = []
    for title, info in CATEGORIES.items():
        kind = _KIND_LABEL.get(info["kind"], info["kind"])
        cards.append(
            f'<div class="card"><div class="title">{title}</div>'
            f'<div class="slug">{info["slug"]} · {kind}</div></div>'
        )
    html = _HTML.replace("{n}", str(len(CATEGORIES)))
    return html.replace("{cards}", "\n".join(cards))


async def render_category_list() -> bytes | None:
    """把分类列表渲染成 PNG 图片。

    Returns:
        PNG bytes；htmlkit 未安装或渲染失败返回 None。
    """
    if not HTMLKIT_AVAILABLE:
        return None
    try:
        require("nonebot_plugin_htmlkit")
        from nonebot_plugin_htmlkit import html_to_pic  # type: ignore[import-not-found]

        return await html_to_pic(_build_html(), max_width=620)
    except Exception:
        return None
