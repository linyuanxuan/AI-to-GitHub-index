#!/usr/bin/env python3
"""一键把当前目录提交并推送到 GitHub。

设计原则：
- 不硬编码任何用户名 / 邮箱 / 仓库地址，全部来自参数或本机 git 配置
- 不保存任何凭据；认证交给系统 git（GCM / SSH key / 环境变量）
- 设置 GIT_TERMINAL_PROMPT=0，绝不因为等密码而卡死；认证失败立刻给可执行建议
- 网络失败时自动探测本地代理并重试一次

用法:
    python publish.py --dir . --remote-url https://github.com/<owner>/<repo>.git \
        --message "feat: init" [--name 名字 --email 邮箱] [--proxy auto|<url>|off] [--dry-run]

退出码:
    0 成功  2 环境问题  3 缺少提交身份  4 需要认证  5 网络/代理  6 推送被拒
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detect_git as dg  # noqa: E402

DEFAULT_GITIGNORE = """\
# 依赖
node_modules/
venv/
.venv/
env/
__pycache__/
*.py[cod]

# 产物
dist/
build/
out/
*.log

# 密钥与本地配置
.env
.env.*
*.pem
*.key
secrets.*

# 系统与编辑器
.DS_Store
Thumbs.db
desktop.ini
.idea/
.vscode/

# 大文件（按需保留）
*.zip
*.tar.gz

# 模型权重（体积大，一律不入库）
*.safetensors
*.ckpt
*.gguf
*.onnx
*.pt
*.pth
# *.bin    # PyTorch 旧版权重；若项目里有正常 .bin 数据文件请注释掉本行
"""

AUTH_HINTS = (
    "authentication failed",
    "could not read username",
    "could not read password",
    "terminal prompts disabled",
    "permission denied (publickey)",
    "support for password authentication",
    "invalid username or password",
    "403",
    "401",
)
NET_HINTS = (
    "connection was reset",
    "connection reset",
    "failed to connect",
    "could not resolve host",
    "recv failure",
    "timed out",
    "timeout",
    "network is unreachable",
    "ssl",
    "early eof",
)
REJECT_HINTS = ("non-fast-forward", "fetch first", "rejected", "behind", "diverged")


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str], cwd: str, timeout: int = 180, env_extra: dict | None = None):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"  # 不让 git 挂在密码输入上
    env["GCM_INTERACTIVE"] = "auto"
    if env_extra:
        env.update(env_extra)
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, env=env)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"命令超时（{timeout}s）：{' '.join(cmd)}"
    except Exception as exc:  # noqa: BLE001
        return 1, "", f"{type(exc).__name__}: {exc}"


def classify(stderr: str) -> str:
    low = (stderr or "").lower()
    if any(h in low for h in AUTH_HINTS):
        return "auth"
    if any(h in low for h in REJECT_HINTS):
        return "reject"
    if any(h in low for h in NET_HINTS):
        return "network"
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser(description="提交并推送当前目录到 GitHub")
    ap.add_argument("--dir", default=os.getcwd(), help="项目目录，默认当前目录")
    ap.add_argument("--remote-url", help="仓库地址，如 https://github.com/<owner>/<repo>.git")
    ap.add_argument("--remote-name", default="origin")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--message", default="chore: 初始化仓库", help="提交信息")
    ap.add_argument("--name", help="提交用户名（不传则用本机 git 配置）")
    ap.add_argument("--email", help="提交邮箱（不传则用本机 git 配置）")
    ap.add_argument("--proxy", default="auto", help="auto（默认）| off | http://127.0.0.1:7890")
    ap.add_argument("--timeout", type=int, default=180, help="单条 git 命令超时秒数")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要执行的动作")
    args = ap.parse_args()

    workdir = str(Path(args.dir).resolve())
    if not Path(workdir).is_dir():
        log(f"[error] 目录不存在: {workdir}")
        return 2

    # ---------- 1. git ----------
    git, version = dg.find_git()
    if not git:
        log("[error] 未找到 git。请先安装 Git 并确保在 PATH 中，或写入 scripts/detect_git.py 的 GIT_CANDIDATES。")
        return 2
    log(f"[1/6] git: {version}  ({git})")

    # ---------- 2. 身份 ----------
    repo_root_probe = dg.detect_repo(git, workdir)
    identity = dg.detect_identity(git, repo_root_probe["root"] if repo_root_probe["in_repo"] else None)
    name = args.name or identity["name"]
    email = args.email or identity["email"]
    if not name or not email:
        log("[error] 缺少提交身份。用 --name/--email 传入，或先执行：")
        log('        git config --global user.name  "你的名字"')
        log('        git config --global user.email "you@example.com"')
        return 3
    log(f"[2/6] 提交身份: {name} <{email}>  (来源: {'参数' if args.name or args.email else identity['source']})")

    # ---------- 3. 仓库 ----------
    repo = dg.detect_repo(git, workdir)
    if not repo["in_repo"]:
        if args.dry_run:
            log(f"[3/6] 将执行: git init -b {args.branch}")
        else:
            code, out, err = run([git, "init", "-b", args.branch], workdir, args.timeout)
            if code != 0:
                log(f"[error] git init 失败: {err}")
                return 2
            log(f"[3/6] 已初始化仓库（分支 {args.branch}）")
    else:
        log(f"[3/6] 已是仓库: {repo['root']}（分支 {repo['branch'] or '未提交'}）")
    root = repo["root"] if repo["in_repo"] else workdir

    # 本地身份（只在仓库内设置，不污染全局）
    if args.name or args.email:
        if not args.dry_run:
            run([git, "config", "--local", "user.name", name], root)
            run([git, "config", "--local", "user.email", email], root)

    # 兜底文件：避免把依赖 / 密钥 / 大文件推上去
    for fname, content in (
        (".gitignore", DEFAULT_GITIGNORE),
        (".gitattributes", "* text=auto eol=lf\n*.bat text eol=crlf\n"),
    ):
        target = Path(root) / fname
        if not target.exists():
            if args.dry_run:
                log(f"        将创建 {fname}")
            else:
                target.write_text(content, encoding="utf-8", newline="\n")
                log(f"        已创建 {fname}")

    # ---------- 4. 提交 ----------
    if args.dry_run:
        n = len([p for p in Path(root).rglob("*") if p.is_file()
                 and ".git" not in p.parts])
        log(f"[4/6] 将暂存全部改动并提交: {args.message}（工作区 {n} 个文件）")
    else:
        run([git, "add", "-A"], root, args.timeout)
        code, _, _ = run([git, "diff", "--cached", "--quiet"], root, args.timeout)
        staged = code != 0
        repo2 = dg.detect_repo(git, root)
        if staged:
            code, out, err = run([git, "commit", "-m", args.message], root, args.timeout)
            if code != 0:
                log(f"[error] 提交失败: {err or out}")
                return 2
            log(f"[4/6] 已提交: {args.message}")
        elif repo2["has_commits"]:
            log("[4/6] 工作区干净，跳过提交")
        else:
            log("[warn] 没有可提交的内容（目录为空？）")
            return 2

    # ---------- 5. 远端 ----------
    if args.remote_url:
        remotes = {r["name"]: r["url"] for r in dg.detect_remotes(git, root)}
        if args.remote_name in remotes:
            if remotes[args.remote_name] != args.remote_url:
                if not args.dry_run:
                    run([git, "remote", "set-url", args.remote_name, args.remote_url], root)
                    log(f"[5/6] 已更新远端 {args.remote_name} -> {args.remote_url}")
                else:
                    log(f"[5/6] 将更新远端 {args.remote_name}: {remotes[args.remote_name]} -> {args.remote_url}")
            else:
                log(f"[5/6] 远端 {args.remote_name} 已指向 {args.remote_url}")
        else:
            if not args.dry_run:
                run([git, "remote", "add", args.remote_name, args.remote_url], root)
                log(f"[5/6] 已添加远端 {args.remote_name} -> {args.remote_url}")
            else:
                log(f"[5/6] 将添加远端 {args.remote_name} -> {args.remote_url}")
    else:
        remotes = {r["name"]: r["url"] for r in dg.detect_remotes(git, root)}
        if args.remote_name not in remotes:
            log(f"[error] 没有远端。用 --remote-url 传入仓库地址。")
            return 2
        log(f"[5/6] 使用已有远端 {args.remote_name}: {remotes[args.remote_name]}")

    # ---------- 6. 推送 ----------
    net = dg.detect_network() if args.proxy.lower() == "auto" else {}

    def candidates() -> list[str]:
        """按优先级返回要尝试的代理地址；空字符串代表直连。"""
        mode = args.proxy.lower()
        if mode == "off":
            return [""]
        if mode != "auto":
            return [args.proxy]
        if net.get("direct_github"):
            return [""]                                    # 直连已验证可用
        if net.get("proxy_ok") and net.get("proxy"):
            return [net["proxy"]]                          # 直连不通，已知可用代理
        # 没验证出代理：把本机在监听的端口都试一遍，再退回直连
        ports = [f"http://127.0.0.1:{p}" for p in net.get("listening_ports", [])]
        return ports or [""]

    push_tail = ["push", "-u", args.remote_name, args.branch]
    plan = candidates()
    if args.dry_run:
        cmd = [git, *(["-c", f"http.proxy={plan[0]}"] if plan[0] else []), *push_tail]
        log(f"[6/6] 将执行: {' '.join(cmd)}")
        return 0

    code, out, err = 1, "", "未尝试任何推送路径"
    for idx, cand in enumerate(plan):
        proxy_args = ["-c", f"http.proxy={cand}", "-c", f"https.proxy={cand}"] if cand else []
        if cand:
            if dg.http_via_proxy(cand) is None:
                log(f"[6/6] 代理 {cand} 不可用，跳过")
                continue
            log(f"[6/6] 使用代理 {cand}")
        code, out, err = run([git, *proxy_args, *push_tail], root, args.timeout * 2)
        if code == 0:
            break
        kind = classify(err or out)
        if kind != "network" or idx == len(plan) - 1:
            break
        log(f"[6/6] 这条路不通（{kind}），换下一条重试")

    if code == 124:
        log("[error] 推送超时。多为认证环节卡住：请在交互终端里手动执行一次 git push 完成登录。")
        return 4
    if code != 0:
        kind = classify(err or out)
        if kind == "auth":
            log("[error] 认证失败。三种解法，任选其一：")
            log("        1) 在普通终端里手动执行一次 git push，让 Git Credential Manager 弹出登录")
            log("        2) 配置 SSH key 并把远端换成 git@github.com:<owner>/<repo>.git")
            log("        3) 生成 Personal Access Token，用 https://<token>@github.com/... 推送（不要提交到仓库）")
            return 4
        if kind == "network":
            first = (err or out).splitlines()[0] if (err or out) else "unknown"
            log(f"[error] 网络不通: {first}")
            if net.get("tcp_github") and not net.get("direct_github"):
                log("        端口 443 能连但 HTTPS 握手失败（SNI 阻断），必须走代理。")
            ports = ", ".join(str(p) for p in net.get("listening_ports", [])) or "无"
            log(f"        本机监听的候选端口: {ports}")
            log("        确认代理已开启后指定：--proxy http://127.0.0.1:<port>")
            return 5
        if kind == "reject":
            log("[error] 远端有新提交，推送被拒。先同步再推：")
            log(f"        git pull --rebase {args.remote_name} {args.branch}")
            return 6
        log(f"[error] 推送失败:\n{err or out}")
        return 6

    log(f"[6/6] 推送成功: {out.splitlines()[-1] if out else 'ok'}")
    parsed = dg.parse_remote(args.remote_url or "")
    if parsed.get("provider") == "github" and parsed.get("owner"):
        log(f"        仓库: https://github.com/{parsed['owner']}/{parsed['repo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
