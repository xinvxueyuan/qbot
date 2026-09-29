"""栗次元 (t.alcy.cc) 分类表与图片拉取逻辑。

接口形态（2026-08 实测）:
- JSON 分类: GET https://t.alcy.cc/json?<slug>=<N>
  -> {"code":200,"category","count","data":[...]}
- 直接端点: GET https://t.alcy.cc/<slug>
  -> 302 到随机图片（无数量参数，需循环请求）
- acg 为视频端点 (video/mp4)，按直接端点处理
- se/semp (14+) 已 404、pixiv 为外部站，不收录
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

BASE_URL = "https://t.alcy.cc"

# 子命令标题 -> 分类定义（标题已去除"自适应"后缀与 PC/移动等技术名）
# kind: json = JSON 接口支持数量；direct = 直接端点，循环取图；video = 视频端点
CATEGORIES: dict[str, dict[str, str]] = {
    "二次元": {"slug": "ycy", "kind": "direct"},
    "萌版": {"slug": "moez", "kind": "direct"},
    "AI": {"slug": "ai", "kind": "json"},
    "原神": {"slug": "ysz", "kind": "direct"},
    "横图": {"slug": "pc", "kind": "json"},
    "萌版横图": {"slug": "moe", "kind": "json"},
    "风景横图": {"slug": "fj", "kind": "json"},
    "风景竖图": {"slug": "fjmp", "kind": "json"},
    "白底横图": {"slug": "bd", "kind": "json"},
    "原神横图": {"slug": "ys", "kind": "json"},
    "ACG动图": {"slug": "acg", "kind": "video"},
    "竖图": {"slug": "mp", "kind": "json"},
    "萌版竖图": {"slug": "moemp", "kind": "json"},
    "原神竖图": {"slug": "ysmp", "kind": "json"},
    "AI竖图": {"slug": "aimp", "kind": "json"},
    "头像方图": {"slug": "tx", "kind": "json"},
    "七濑胡桃": {"slug": "lai", "kind": "json"},
    "小狐狸": {"slug": "xhl", "kind": "json"},
}

# slug 反向索引（允许用户直接输 pc/moe 等）
SLUG_TO_TITLE: dict[str, str] = {
    info["slug"]: title for title, info in CATEGORIES.items()
}

MAX_COUNT = 50
TIMEOUT = httpx.Timeout(20.0)
# 网络抖动重试：最多尝试 RETRY_TIMES 次，间隔指数退避
RETRY_TIMES = 3
RETRY_BASE_DELAY = 1.0

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}


@dataclass
class Category:
    """解析后的分类。"""

    title: str
    slug: str
    kind: str


def resolve_category(word: str) -> Category | None:
    """按子命令标题或 slug 解析分类。

    Args:
        word: 用户输入（标题如"二次元"，或 slug 如"ycy"）。

    Returns:
        解析成功返回 Category，否则 None。
    """
    if word in CATEGORIES:
        info = CATEGORIES[word]
        return Category(title=word, slug=info["slug"], kind=info["kind"])
    if word in SLUG_TO_TITLE:
        title = SLUG_TO_TITLE[word]
        info = CATEGORIES[title]
        return Category(title=title, slug=word, kind=info["kind"])
    return None


def category_list_text() -> str:
    """可用子命令列表（帮助用）。"""
    lines = ["可用分类："]
    for title, info in CATEGORIES.items():
        lines.append(f"  {title} ({info['slug']})")
    return "\n".join(lines)


async def fetch_images(cat: Category, count: int) -> list[str]:
    """拉取指定分类的图片链接列表（带网络抖动重试）。

    Args:
        cat: 分类。
        count: 数量（json 分类一次请求；direct/video 分类循环请求）。

    Returns:
        图片/视频 URL 列表。

    Raises:
        httpx.HTTPError: 网络错误（重试耗尽后）。
        ValueError: 接口返回异常。
    """
    count = max(1, min(count, MAX_COUNT))
    last_exc: Exception | None = None
    for attempt in range(RETRY_TIMES):
        try:
            if cat.kind == "json":
                return await _fetch_json(cat.slug, count)
            return await _fetch_direct(cat.slug, count)
        except (httpx.HTTPError, ValueError) as e:  # noqa: PERF203
            last_exc = e
            if attempt < RETRY_TIMES - 1:
                await asyncio.sleep(RETRY_BASE_DELAY * (2**attempt))
    assert last_exc is not None
    raise last_exc


async def _fetch_json(slug: str, count: int) -> list[str]:
    """JSON 分类：一次请求返回 count 条。"""
    url = f"{BASE_URL}/json?{slug}={count}"
    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    if data.get("code") != 200:
        msg = f"接口返回异常 code={data.get('code')}"
        raise ValueError(msg)
    raw = data.get("data", [])
    if isinstance(raw, dict):
        raw = [raw]
    links = [
        item["link"] for item in raw if isinstance(item, dict) and item.get("link")
    ]
    if not links:
        msg = f"分类 {slug} 未返回任何链接"
        raise ValueError(msg)
    return links


async def _fetch_direct(slug: str, count: int) -> list[str]:
    """直接端点：循环请求拿 count 张（每次 302 到随机资源）。

    附加 ?postId=<n> 参数：参考官方文章，同一 URL 加不同参数可绕过
    浏览器/代理缓存拿到不同图片（https://www.alcy.cc/archives/sui-ji-er-ci-yuan-tu-pian-api）。
    """
    url = f"{BASE_URL}/{slug}"
    links: list[str] = []
    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        for i in range(count):
            resp = await client.get(url, params={"postId": i + 1})
            resp.raise_for_status()
            final = str(resp.url)
            # 部分资源可能是 mp4/图片混排，全部按链接返回
            links.append(final)
    return links
