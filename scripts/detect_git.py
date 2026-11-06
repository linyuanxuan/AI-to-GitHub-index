#!/usr/bin/env python3
"""探测本机 git 环境，输出 JSON，供上层决定怎么用。

不依赖任何第三方库，不读取、不输出任何凭据内容。

用法:
    python detect_git.py                 # 探测当前目录
    python detect_git.py --dir <path>    # 探测指定目录

输出字段见 README 或 SKILL.md；关键项:
    git.path / git.version       git 可执行文件位置与版本
    repo.in_repo / root / branch 是否在仓库内、仓库根、当前分支
    identity.name / email / source  提交身份（repo → global → env → none）
    remote.url / provider / owner / repo  远端地址与解析结果
    network.direct_github        是否能直连 github.com:443
    network.proxy                探测到的可用代理（env 或常见本地端口）
    advice                       人话建议列表
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

IS_WIN = os.name == "nt"

GIT_CANDIDATES = [
    # Windows
    r"C:\Program Files\Git\cmd\git.exe",
    r"C:\Program Files (x86)\Git\cmd\git.exe",
    r"C:\Program Files\Git\bin\git.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
    # macOS
    "/opt/homebrew/bin/git",
    "/usr/local/bin/git",
    "/usr/bin/git",
    # Linux
    "/usr/bin/git",
    "/bin/git",
]

PROXY_PORTS = [7890, 7891, 7897, 10808, 10809, 1080, 2080, 8080, 8888, 33210]


def find_git() -> tuple[str | None, str | None]:
    """返回 (git 路径, 版本字符串)。"""
    found = shutil.which("git")
    if not found:
        for cand in GIT_CANDIDATES:
            if cand and Path(cand).exists():
                found = cand
                break
    if not found:
        return None, None
    try:
        out = subprocess.run(
            [found, "--version"], capture_output=True, text=True, timeout=15
        ).stdout.strip()
    except Exception:
        out = None
    return found, out


def run_git(git: str, args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            [git, *args], cwd=cwd, capture_output=True, text=True, timeout=60
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as exc:  # noqa: BLE001
        return 1, "", f"{type(exc).__name__}: {exc}"


def detect_repo(git: str, workdir: str) -> dict:
    code, root, _ = run_git(git, ["rev-parse", "--show-toplevel"], cwd=workdir)
    info: dict = {"in_repo": code == 0, "root": root or None, "branch": None,
                  "has_commits": False, "dirty_files": 0}
    if code != 0:
        return info
    c, br, _ = run_git(git, ["rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    if c == 0:
        info["branch"] = br
    c, _, _ = run_git(git, ["rev-parse", "--verify", "HEAD"], cwd=root)
    info["has_commits"] = c == 0
    c, out, _ = run_git(git, ["status", "--porcelain"], cwd=root)
    if c == 0:
        info["dirty_files"] = len([ln for ln in out.splitlines() if ln.strip()])
    return info


def git_config(git: str, key: str, scope: str, cwd: str | None = None) -> str | None:
    args = ["config"]
    if scope == "local":
        args.append("--local")
    elif scope == "global":
        args.append("--global")
    args.append(key)
    code, out, _ = run_git(git, args, cwd=cwd)
    return out or None


def detect_identity(git: str, repo_root: str | None) -> dict:
    """优先级: repo local → global → 环境变量。全部为空时 source=none。"""
    for scope in ("local", "global"):
        if scope == "local" and not repo_root:
            continue
        name = git_config(git, "user.name", scope, cwd=repo_root)
        email = git_config(git, "user.email", scope, cwd=repo_root)
        if name or email:
            return {"name": name, "email": email, "source": scope}
    env_name = os.environ.get("GIT_AUTHOR_NAME") or os.environ.get("GIT_COMMITTER_NAME")
    env_mail = os.environ.get("GIT_AUTHOR_EMAIL") or os.environ.get("GIT_COMMITTER_EMAIL")
    if env_name or env_mail:
        return {"name": env_name, "email": env_mail, "source": "env"}
    return {"name": None, "email": None, "source": "none"}


def parse_remote(url: str) -> dict:
    """解析 https / ssh / scp 形式的远端地址。"""
    provider = "other"
    owner = repo = None
    raw = url.strip()

    if raw.startswith("git@") and ":" in raw:  # git@github.com:owner/repo.git
        host, path = raw[4:].split(":", 1)
        provider = "github" if "github" in host else host
    elif "://" in raw:
        rest = raw.split("://", 1)[1]
        host_path = rest.split("@")[-1]
        host, _, path = host_path.partition("/")
        provider = "github" if "github" in host else host
    else:
        path = raw

    if path:
        path = path.rstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            owner, repo = parts[-2], parts[-1]
    return {"url": url, "provider": provider, "owner": owner, "repo": repo}


def detect_remotes(git: str, repo_root: str) -> list[dict]:
    code, out, _ = run_git(git, ["remote", "-v"], cwd=repo_root)
    remotes: dict[str, str] = {}
    if code == 0:
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                remotes.setdefault(parts[0], parts[1])  # 每个 remote 取第一条 (fetch)
    return [{"name": k, **parse_remote(v)} for k, v in remotes.items()]


def tcp_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_via_proxy(proxy: str, target: str = "https://api.github.com/", timeout: float = 6.0) -> int | None:
    """经代理发一次 HTTPS 请求，返回状态码；失败返回 None。仅用于验证代理可用。"""
    import urllib.error
    import urllib.request

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    )
    req = urllib.request.Request(target, method="GET", headers={"User-Agent": "git-detect"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code  # 401/403 也说明网络通
    except Exception:  # noqa: BLE001
        return None


def detect_network() -> dict:
    info = {
        "direct_github": tcp_open("github.com", 443, 3.0),
        "env_proxy": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"),
        "listening_ports": [],
        "proxy": None,
        "proxy_ok": False,
    }
    for port in PROXY_PORTS:
        if tcp_open("127.0.0.1", port, 0.4):
            info["listening_ports"].append(port)

    candidates = []
    if info["env_proxy"]:
        candidates.append(info["env_proxy"])
    for port in info["listening_ports"]:
        candidates.append(f"http://127.0.0.1:{port}")

    if not info["direct_github"]:
        for cand in candidates:
            code = http_via_proxy(cand)
            if code is not None:
                info["proxy"] = cand
                info["proxy_ok"] = True
                break
    return info


def build_advice(result: dict) -> list[str]:
    advice: list[str] = []
    if not result.get("git", {}).get("path"):
        advice.append("未找到 git：安装 Git 后重试，或把 git 路径写入 PATH。")
        return advice
    if not result.get("repo", {}).get("in_repo"):
        advice.append("当前目录还不是 git 仓库：需要 git init。")
    if result.get("identity", {}).get("source") == "none":
        advice.append("提交身份缺失：用 --name/--email 传入，或先 git config --global user.name/user.email。")
    if not result.get("remotes"):
        advice.append("没有配置远端：用 --remote-url 传入仓库地址。")

    net = result.get("network") or {}
    if net.get("direct_github") is False:
        if net.get("proxy_ok"):
            advice.append(
                f"github.com 直连不通，但检测到可用代理 {net['proxy']}："
                f"推送时传 --proxy {net['proxy']}。"
            )
        else:
            advice.append("github.com 直连不通且没探测到可用代理：先开代理，再传 --proxy <url>。")
    return advice


def main() -> int:
    ap = argparse.ArgumentParser(description="探测 git 环境（输出 JSON）")
    ap.add_argument("--dir", default=os.getcwd(), help="要探测的目录，默认当前目录")
    ap.add_argument("--no-network", action="store_true", help="跳过网络探测，更快")
    args = ap.parse_args()

    workdir = str(Path(args.dir).resolve())
    git_path, git_version = find_git()
    result = {
        "os": {"platform": platform.system(), "release": platform.release()},
        "workdir": workdir,
        "git": {"path": git_path, "version": git_version},
    }
    if not git_path:
        result["advice"] = build_advice(result | {"repo": {"in_repo": False}, "identity": {"source": "none"}, "remotes": [], "network": {"direct_github": False, "proxy_ok": False}})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    repo = detect_repo(git_path, workdir)
    result["repo"] = repo
    result["identity"] = detect_identity(git_path, repo["root"] if repo["in_repo"] else None)
    result["remotes"] = detect_remotes(git_path, repo["root"]) if repo["in_repo"] else []
    result["network"] = (
        {"skipped": True} if args.no_network else detect_network()
    )
    result["advice"] = build_advice(result)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
