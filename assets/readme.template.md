# {{PROJECT}} · {{TAGLINE}}

> {{LEAD}}

[![GitHub](https://img.shields.io/badge/GitHub-{{OWNER}}%2F{{REPO_NAME}}-181717?logo=github)]({{REPO_URL}})
{{#IF_SITE_URL}}[![Live](https://img.shields.io/badge/%E5%9C%A8%E7%BA%BF%E4%BB%8B%E7%BB%8D%E9%A1%B5-{{SITE_HOST}}-5fd3c4)]({{SITE_URL}})
{{/IF_SITE_URL}}![License](https://img.shields.io/badge/license-{{LICENSE}}-blue)

{{#IF_SITE_URL}}**在线介绍页**：{{SITE_URL}}
{{/IF_SITE_URL}}
---

## 这是什么

{{INTRO}}

## 特性

| | |
|---|---|
{{#FEATURES}}| {{TITLE}} | {{DESC_PLAIN}} |
{{/FEATURES}}
## 快速开始

{{#STEPS}}### {{N}}. {{TITLE}}

```bash
{{CODE_PLAIN}}
```

{{NOTE}}

{{/STEPS}}## 使用说明

{{USAGE}}

## 规格

| 项 | 值 |
|---|---|
{{#SPECS}}| {{K}} | {{V}} |
{{/SPECS}}
## 项目结构

```
{{PROJECT}}/
{{TREE}}
```

## 已知限制

{{#LIMITS}}- **{{TITLE}}**：{{DESC}}
{{/LIMITS}}
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

Settings → Pages → Source 选 `main` + `/ (root)`，站点即 `https://{{OWNER_LOWER}}.github.io/{{REPO_NAME}}/`。

> 两者都只托管静态介绍页，不会运行项目后端。

## License

{{LICENSE}} · 详见 [LICENSE](LICENSE)。

---

<sub>{{FOOTER_NOTE}}</sub>
