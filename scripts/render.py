#!/usr/bin/env python3
"""把 JSON 配置渲染成单文件介绍页 / README。

极简模板引擎，只用标准库：
    {{KEY}}              变量替换（输出前做 HTML 转义，除非键以 RAW_ 开头）
    {{#BLOCK}}...{{/BLOCK}}   列表块，内部按每个 item 的字段重复替换
    {{#IF_KEY}}...{{/IF_KEY}} 当 KEY 非空时保留，否则整段删除

用法：
    python render.py --template assets/landing.template.html \
                     --config site.json --out index.html
    python render.py --template assets/readme.template.md \
                     --config site.json --out README.md --no-escape

字段缺失时输出空串而不是报错，方便先出草稿再补内容。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

VAR_RE = re.compile(r"\{\{\s*([A-Za-z0-9_\.]+)\s*\}\}")
BLOCK_RE = re.compile(r"\{\{#([A-Za-z0-9_]+)\}\}(.*?)\{\{/\1\}\}", re.S)


def upper_keys(node):
    """配置键统一转大写，模板里用 {{PROJECT}} 对应 JSON 的 project。"""
    if isinstance(node, dict):
        return {str(k).upper(): upper_keys(v) for k, v in node.items()}
    if isinstance(node, list):
        return [upper_keys(v) for v in node]
    return node


def derive(config: dict) -> dict:
    """补齐可推导的字段，避免用户重复填写，也避免模板残留 {{...}}。"""
    from urllib.parse import urlparse

    cfg = dict(config)
    owner = str(cfg.get("OWNER") or "").strip()
    repo = str(cfg.get("REPO_NAME") or "").strip()
    site = str(cfg.get("SITE_URL") or "").strip()

    # 从 repo_url 反推 owner / repo
    if not owner or not repo:
        url = str(cfg.get("REPO_URL") or "").strip().rstrip("/")
        parts = [p for p in url.replace(":", "/").split("/") if p][-2:]
        if len(parts) == 2:
            owner = owner or parts[0]
            repo = repo or (parts[1][:-4] if parts[1].endswith(".git") else parts[1])
            cfg.setdefault("OWNER", owner)
            cfg.setdefault("REPO_NAME", repo)

    if owner and repo and not cfg.get("REPO_URL"):
        cfg["REPO_URL"] = f"https://github.com/{owner}/{repo}"
    elif str(cfg.get("REPO_URL") or "").endswith(".git"):
        cfg["REPO_URL"] = str(cfg["REPO_URL"])[:-4].rstrip("/")

    if not cfg.get("OWNER_LOWER"):
        cfg["OWNER_LOWER"] = owner.lower()
    if not cfg.get("REPO_LOWER"):
        cfg["REPO_LOWER"] = repo.lower()

    if not cfg.get("SITE_HOST") and site:
        try:
            cfg["SITE_HOST"] = urlparse(site).netloc or site
        except ValueError:
            cfg["SITE_HOST"] = site
    if not cfg.get("PROJECT"):
        cfg["PROJECT"] = repo or "Project"
    return cfg


def esc(value, no_escape: bool) -> str:
    text = "" if value is None else str(value)
    return text if no_escape else html.escape(text, quote=True)


def lookup(key: str, ctx) -> object:
    cur = ctx
    for part in key.split("."):
        part = part.upper()
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return ""
    return cur


def render(template: str, config: dict, no_escape: bool = False, _depth: int = 0) -> str:
    if _depth > 6:
        return template

    # 1. 条件块：{{#IF_KEY}} 当 KEY 为空 / 空列表 / False 时整段删除
    def cond_sub(match: re.Match) -> str:
        raw_key, body = match.group(1), match.group(2)
        key = raw_key[3:] if raw_key.upper().startswith("IF_") else raw_key
        value = lookup(key, config)
        if value in ("", None, False, [], {}):
            return ""
        return render(body, config, no_escape, _depth + 1)

    out = re.sub(r"\{\{#IF_([A-Za-z0-9_]+)\}\}(.*?)\{\{/IF_\1\}\}", cond_sub, template, flags=re.S)

    # 2. 列表块：对每个 item 递归渲染块体
    def block_sub(match: re.Match) -> str:
        key, body = match.group(1), match.group(2)
        items = lookup(key, config)
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            return ""
        chunks = []
        for item in items:
            scope = dict(config)
            if isinstance(item, dict):
                scope.update(item)
            else:
                scope["this"] = item
            chunks.append(render(body, scope, no_escape, _depth + 1))
        return "".join(chunks)

    out = BLOCK_RE.sub(block_sub, out)

    # 3. 变量替换
    def var_sub(match: re.Match) -> str:
        key = match.group(1)
        value = lookup(key, config)
        if key.startswith("RAW_"):
            return "" if value is None else str(value)
        return esc(value, no_escape)

    return VAR_RE.sub(var_sub, out)


def main() -> int:
    ap = argparse.ArgumentParser(description="JSON + 模板 → 单文件页面")
    ap.add_argument("--template", required=True, help="模板文件路径")
    ap.add_argument("--config", required=True, help="JSON 配置文件路径")
    ap.add_argument("--out", required=True, help="输出文件路径")
    ap.add_argument("--no-escape", action="store_true", help="不转义（生成 Markdown 时用）")
    args = ap.parse_args()

    tpl_path = Path(args.template)
    cfg_path = Path(args.config)
    for p in (tpl_path, cfg_path):
        if not p.exists():
            print(f"[error] 文件不存在: {p}", file=sys.stderr)
            return 2

    template = tpl_path.read_text(encoding="utf-8")
    config = derive(upper_keys(json.loads(cfg_path.read_text(encoding="utf-8"))))
    output = render(template, config, no_escape=args.no_escape)

    leftover = sorted(set(VAR_RE.findall(output)))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8", newline="\n")

    print(f"[ok] {out_path}  {len(output.encode('utf-8'))} bytes")
    if leftover:
        print(f"[warn] 模板里有未赋值的变量: {', '.join(leftover)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
