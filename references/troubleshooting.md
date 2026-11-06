# 排错：publish.py 退出码与常见报错

## 退出码

| 码 | 含义 | 处理 |
|---|---|---|
| 0 | 成功 | — |
| 2 | 环境问题（找不到 git / 目录不存在 / 没有可提交内容 / commit 失败） | 按打印的提示修 |
| 3 | 缺少提交身份 | 传 `--name --email`，或先 `git config --global user.name/user.email` |
| 4 | 需要认证（push 被拒 401/403，或认证环节超时） | 见下方「认证失败」 |
| 5 | 网络不通 | 见下方「网络不通」 |
| 6 | 推送被拒（远端有新提交） | 见下方「推送被拒」 |

## 认证失败（退出码 4）

脚本设了 `GIT_TERMINAL_PROMPT=0`，所以不会卡在密码输入上，而是直接失败。三条路，任选其一：

**1. 交互式登录一次（推荐）**

让用户在普通终端里手动跑一次：

```bash
cd <项目目录>
git push -u origin main
```

Git Credential Manager 会弹浏览器登录，成功后凭据进系统钥匙串，之后脚本也能复用。

**2. SSH**

```bash
ssh-keygen -t ed25519 -C "<邮箱>"
# 把 ~/.ssh/id_ed25519.pub 内容贴到 GitHub → Settings → SSH and GPG keys
git remote set-url origin git@github.com:<owner>/<repo>.git
```

**3. Personal Access Token**

GitHub → Settings → Developer settings → Tokens (classic) → 勾 `repo`。
用 `https://<token>@github.com/<owner>/<repo>.git` 作为远端**只在命令行内联使用**，不要写进 `.git/config` 或脚本。
用完即 `git remote set-url origin https://github.com/<owner>/<repo>.git` 清除。

> 不要把 token 贴进聊天记录、提交、README。

## 网络不通（退出码 5）

典型报错：

- `Recv failure: Connection was reset`
- `Failed to connect to github.com port 443`
- `Could not resolve host: github.com`
- `SSL_connect ... unexpected eof`

处理顺序：

1. 先确认代理已开启。`detect_git.py` 会列出 `network.listening_ports`（常见 7890 / 7891 / 10808）。
2. 手动指定：`--proxy http://127.0.0.1:7890`。
3. 验证代理真的能到 GitHub：

   ```bash
   curl -x http://127.0.0.1:7890 -o /dev/null -w "%{http_code}\n" https://github.com
   ```

   返回 200 才算通；`000` 是没通。

4. 若只想让本仓库走代理（不影响全局）：

   ```bash
   git config http.proxy http://127.0.0.1:7890
   ```

   关代理后要撤：`git config --unset http.proxy && git config --unset https.proxy`。

## 推送被拒（退出码 6）

报错含 `non-fast-forward` / `rejected` / `fetch first`：远端已有本地没有的提交。

```bash
git pull --rebase origin main
git push -u origin main
```

若确认远端提交可丢弃（例如远端是自动生成的 README），再考虑 `git push -f`——**先问用户**，force push 会覆盖别人的工作。

## 渲染阶段

**配置文件里的 `{{` 被吞掉**

`site.json` 是模板的数据源，值里出现 `{{` 会被二次当作变量/块语法处理：`{{KEY}}` 直接渲染成空串，`{{#X}}` 若后面正好有 `{{/X}}` 会把中间内容整段吃掉。

要表达模板语法本身，用文字描述（「双花括号：变量 / 列表块 / 条件块」），不要写原始 token。

**渲染后仍有 `{{`**

先分清两类：

```bash
grep -o "{{[^}]*}}" index.html README.md | sort -u
```

- 出现完整变量名（`{{TAGLINE}}` 之类）→ 配置漏填，补 `site.json` 后重跑
- 只有 `{{#LIST}}` 这类半个块 → 多数是文案里写了模板 token，同上，改文案

## 其他

**`git init` 后默认分支是 master**

脚本用 `git init -b main` 直接指定分支；老版本 git 不支持 `-b` 时手动 `git branch -M main`。

**提交被 .gitignore 全挡掉，提示没有可提交内容**

脚本只在 `.gitignore` 不存在时创建兜底版本。若项目已有 `.gitignore` 把新文件挡了：

```bash
git check-ignore -v <文件路径>
```

**Windows 下 .bat 乱码**

批处理文件必须纯 ASCII + CRLF。检查：

```bash
LC_ALL=C grep -nP '[^\x00-\x7F]' xxx.bat   # 有输出就是有非 ASCII
python -c "p='x.bat';d=open(p,'rb').read().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n');open(p,'wb').write(d)"
```
