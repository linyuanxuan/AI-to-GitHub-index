# github-showcase-publish · 把本地项目变成带介绍页的 GitHub 仓库

> 读你的代码，生成 README.md 与单文件 index.html，再完成 init / commit / push。用户名、邮箱、仓库地址、代理全部当场探测，一个都不写死在代码里。

[![GitHub](https://img.shields.io/badge/GitHub-linyuanxuan%2FAI-to-GitHub-index-181717?logo=github)](https://github.com/linyuanxuan/AI-to-GitHub-index)
![License](https://img.shields.io/badge/license-MIT-blue)


---

## 这是什么

开源项目最难的不是写代码，是写那份没人愿意写的 README。这个 skill 把「读代码 → 写文档 → 做介绍页 → 推上去」串成一条可执行流程。

它不渲染模型生成的空话：特性、命令、规格都来自实际读到的文件。介绍页是单文件 HTML，纯静态，GitHub Pages 与 Cloudflare Pages 都能直接托管。

与「让 AI 直接写个 README」的区别在于可复现——同样的配置跑两次，产出一模一样；版式不满意改模板，不用重新生成。

## 特性

| | |
|---|---|
| 先探测，再动手 | git 装在哪、提交身份是谁、远端指向哪里、要不要走代理，一次问清楚。 |
| 零硬编码个人信息 | 代码里没有用户名、邮箱和仓库地址，全部来自 git config 或当场传参。 |
| 模板 + JSON 渲染 | 极简模板引擎，支持变量、列表块和条件块，改版式不用碰 Python。 |
| 认证不卡死 | 关闭终端密码提示，认证失败立刻返回退出码与三条可执行方案。 |
| 代理自动回退 | 直连失败时扫描常见本地代理端口，逐个验证后再用于推送。 |
| dry-run 先演练 | 加 --dry-run 只打印将执行的动作，不改文件、不建仓库、不推送。 |

## 快速开始

### 1. 放进 skills 目录

```bash
git clone https://github.com/linyuanxuan/AI-to-GitHub-index.git ~/.workbuddy/skills/github-showcase-publish
```

装成用户级 skill，所有项目都能调用；也可放项目内的 .workbuddy/skills/。

### 2. 填配置并渲染

```bash
cp assets/site.example.json site.json
python scripts/render.py --template assets/readme.template.md --config site.json --out README.md --no-escape
python scripts/render.py --template assets/landing.template.html --config site.json --out index.html
```

脚本会列出没赋值的变量名，补齐后重跑即可。

### 3. 提交并推送

```bash
python scripts/publish.py --dir . --remote-url https://github.com/<owner>/<repo>.git --message "feat: README + 介绍页"
```

先加 --dry-run 演练一遍更稳。身份缺省时读本机 git config。

## 使用说明

三个脚本各自独立，也能单独用：`detect_git.py` 输出 JSON 供别的程序消费，`render.py` 只管模板渲染，`publish.py` 只管提交推送。串起来是一条流水线，拆开是三把小刀。

## 规格

| 项 | 值 |
|---|---|
| 运行时 | Python 3.8+（纯标准库） |
| 第三方依赖 | 0 |
| 整包体积 | 约 85 KB |
| 模板语法 | 双花括号：变量 / 列表块 / 条件块 |
| 退出码 | 0 成功 / 2 环境 / 3 身份 / 4 认证 / 5 网络 / 6 被拒 |
| 许可 | MIT |

## 项目结构

```
github-showcase-publish/
├── SKILL.md               # 流程、铁律、常见坑
├── scripts/
│   ├── detect_git.py      # 环境探测 → JSON
│   ├── render.py          # 模板 + JSON → 文件
│   └── publish.py         # init / commit / remote / push
├── assets/
│   ├── landing.template.html
│   ├── readme.template.md
│   ├── site.example.json
│   └── _headers.example
└── references/
    ├── config-schema.md
    └── troubleshooting.md
```

## 已知限制

- **不替你建远端仓库**：创建 GitHub 仓库要走 API，需要你的 token。它只负责往已存在的仓库推。
- **不替你登录**：认证交给系统 git（Credential Manager / SSH key）。凭据不进任何文件，也不经过脚本。
- **介绍页是静态的**：只有 HTML/CSS/JS，没有后端。项目本身的功能得在本地跑。
- **内容要人来审**：特性、规格、限制这些事实来自读代码，但措辞和取舍仍需要你过一眼，它不会替你吹。

## 常见问题

<details>
<summary>部署这份介绍页需要什么</summary>

`index.html` 是纯静态单文件，无构建步骤。GitHub Pages / Cloudflare Pages / Vercel 都能直接托管：构建设置留空，输出目录填根目录即可。
</details>

<details>
<summary>介绍页会运行后端代码吗</summary>

不会。静态托管只负责展示；项目功能仍需在本地运行。
</details>

## 部署介绍页

`index.html` 是纯静态单文件，无构建步骤，任何静态托管都能直接放。

### Cloudflare Pages（推荐，可用自定义域名）

| 项 | 值 |
|---|---|
| Framework preset | **None** |
| Build command | 留空 |
| Build output directory | `/` |
| 分支 | `main` |

Connect to Git 选中本仓库后保存即可，之后每次 push 自动重新部署。绑定域名：项目 → **Custom domains** → 输入子域，域名也在 Cloudflare 时 DNS 记录会自动创建。

根目录的 `_headers` 会被 Cloudflare Pages 识别，用于设置 `index.html` 的短缓存与安全响应头。

### GitHub Pages（备选）

Settings → Pages → Source 选 `main` + `/ (root)`，站点即 `https://linyuanxuan.github.io/AI-to-GitHub-index/`。

> 两者都只托管静态介绍页，不会运行项目后端。

## License

MIT · 详见 [LICENSE](LICENSE)。

---

<sub>在 2 核 Windows 机器上边跑边修出来的。</sub>
