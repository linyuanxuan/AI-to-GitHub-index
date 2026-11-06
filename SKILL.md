---
name: github-showcase-publish
description: 为一个代码项目生成 README.md 与单文件介绍页 index.html，然后初始化 git 仓库、提交并推送到 GitHub。当用户说「给我的项目写个 README 和介绍网页」「做个项目主页并传到 GitHub」「把这个项目开源出去」「push 到仓库」时使用。自动探测 git 安装位置、提交身份、远端地址与本地代理，不硬编码任何用户名、邮箱或仓库地址。
---

# GitHub 项目展示页生成与发布

把一个本地项目变成「有 README、有介绍页、已经推到 GitHub」的状态。三步：取项目事实 → 渲染 README 与介绍页 → 提交推送。

## 何时使用

- 「给这个项目写 README / 做个介绍网站，然后传到 GitHub」
- 「这个仓库还没有首页，帮我补上并推上去」
- 「把本地项目初始化成仓库推到 GitHub」

不适用：只改文案（直接编辑文件即可）、需要后端服务的动态站点。

## 铁律

1. **不写死用户名、邮箱、仓库地址**。身份从 `git config` 或用户当场给的参数来；仓库地址从 `git remote` 或用户输入来。缺失就问，别猜。
2. **不把凭据写进任何文件**。认证交给系统 git（Credential Manager / SSH key / 环境变量）。
3. **推送前先探测网络**。GitHub 在部分网络下直连不通，需要本地代理；探测到就用，探测不到就明确提示用户开代理。
4. **提交前确认没有敏感/超大文件**。模型权重、`node_modules`、`.env` 不能进仓库。

## 流程

### 步骤 1：采集项目事实（不要跳过）

先跑探测脚本，拿到机器与仓库的真实状态：

```bash
python scripts/detect_git.py --dir <项目目录>
```

关键字段：

| 字段                                        | 用途                            |
| ----------------------------------------- | ----------------------------- |
| `git.path`                                | 后续所有 git 命令用这个绝对路径，避开 PATH 问题 |
| `repo.in_repo` / `repo.root`              | 决定是否需要 `git init`             |
| `identity.name/email/source`              | 提交身份；`source=none` 时向用户索取     |
| `remotes[].url/owner/repo`                | 已配远端就沿用，别覆盖                   |
| `network.direct_github` / `network.proxy` | 决定推送是否需要代理                    |

同时读项目本身：入口文件、依赖清单（`package.json` / `requirements.txt` / `pyproject.toml`）、已有 README、目录结构。**介绍页里的特性、命令、规格必须来自真实代码**，不允许编造。

### 步骤 2：填写配置

```bash
cp assets/site.example.json site.json
```

字段说明见 `references/config-schema.md`。要点：

- `repo_url` 必填，格式 `https://github.com/<owner>/<repo>`；填了它 `owner` / `repo_name` / `site_host` 会自动推导，不用重复写
- `site_url` 有自定义域名就填，没有留空（模板自动隐藏相关按钮）
- `stats` / `features` / `specs` / `limits` 各 3–6 条，宁少勿虚
- `limits` 必须写真实限制，这是可信度来源
- `term_lines` 用真实跑出来的输出，不要编
- **值里不要写 `{{`**：会被模板引擎当成变量吞掉，想描述语法就用文字说

### 步骤 3：渲染两个文件

```bash
python scripts/render.py --template assets/readme.template.md --config site.json --out README.md --no-escape
python scripts/render.py --template assets/landing.template.html --config site.json --out index.html
```

脚本会打印未赋值的变量名，补齐后重跑。模板语法：

- `{{KEY}}` 变量（配置键大小写不敏感）
- `{{#BLOCK}}...{{/BLOCK}}` 列表重复
- `{{#IF_KEY}}...{{/IF_KEY}}` 条件块，KEY 为空则整段删除

渲染后**必须自查**：`grep -o "{{[^}]*}}" index.html README.md` 应为空；用预览面板看一眼 `index.html`，确认排版没塌。

若打算用 Cloudflare Pages，额外把 `assets/_headers.example` 复制成项目根目录的 `_headers`，用于设置缓存与安全响应头。

模板是可改的起点。项目气质不匹配时改 CSS 变量或删整段，比硬套更像人做的。

### 步骤 4：提交推送

```bash
python scripts/publish.py --dir <项目目录> \
  --remote-url https://github.com/<owner>/<repo>.git \
  --message "feat: 项目初始化（README + 介绍页）" \
  [--name 名字 --email 邮箱] \
  [--proxy auto]
```

六步逐步打印：`git` → 身份 → 仓库（必要时 init）→ 提交（必要时创建 `.gitignore`/`.gitattributes`）→ 远端 → 推送。默认 `--proxy auto`，直连失败会自动找本地代理重试。

拿不准时先加 `--dry-run`：只打印将执行的动作，不改文件、不建仓库、不推送。

自动生成的 `.gitignore` 已挡住 `node_modules` / `venv` / `.env` / `*.safetensors` / `*.pt` 等；项目已有 `.gitignore` 时不会覆盖。

**认证不会卡死**：脚本设 `GIT_TERMINAL_PROMPT=0`，认证失败立刻返回退出码 4 和三条可执行方案，不会挂在密码提示上。

退出码与报错处理见 `references/troubleshooting.md`。

### 步骤 5：交付说明

推送成功后告诉用户三件事：

1. 仓库地址与分支
2. 是否要开 Pages（GitHub：Settings → Pages → `main` + `/ (root)`；Cloudflare Pages：构建命令留空、输出目录 `/`）
3. 若代理写进了 `.git/config`，关代理后要 `git config --unset http.proxy`

## 脚本

| 脚本                      | 作用                                                   |
| ----------------------- | ---------------------------------------------------- |
| `scripts/detect_git.py` | 探测 git 路径、仓库状态、提交身份、远端、网络与代理，输出 JSON                 |
| `scripts/render.py`     | 模板 + JSON → README / index.html，含未赋值变量告警             |
| `scripts/publish.py`    | init / config / commit / remote / push 全流程，错误分类与代理回退 |

## 资源

| 文件                              | 用途                               |
| ------------------------------- | -------------------------------- |
| `assets/landing.template.html`  | 深色单页介绍页模板，响应式、无外部依赖、含复制按钮与滚动渐入   |
| `assets/readme.template.md`     | README 骨架，含徽章、特性表、快速开始、规格、限制、FAQ |
| `assets/site.example.json`      | 配置样例，字段齐全                        |
| `assets/_headers.example`       | Cloudflare Pages 的缓存与安全响应头模板     |
| `references/config-schema.md`   | 配置字段逐项说明                         |
| `references/troubleshooting.md` | 退出码、报错分类与处理                      |

## 常见坑

- **Windows 下 .bat 乱码**：批处理必须纯 ASCII + CRLF。用 UTF-8 存中文会让 cmd 按 GBK 解析成乱码命令。`.gitattributes` 已声明 `*.bat text eol=crlf`。
- **镜像缺新版本 wheel**：装依赖报 `No matching distribution found` 时换 `https://mirrors.aliyun.com/pypi/simple`。  
  |  |  |  |  |  |  
  | --- | --- | --- | --- | --- |
- **大文件误入库**：推送前 `git ls-files | grep -E '\.(bin|safetensors|zip|pt)$'` 自查。
- **覆盖用户已有远端**：`publish.py` 只在地址不同时 `set-url`，且地址必须显式传入。
