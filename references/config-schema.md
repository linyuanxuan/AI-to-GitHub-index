# site.json 字段说明

配置键大小写不敏感（`project` 与 `PROJECT` 等价）。所有字段都可缺省，缺省渲染成空串。

**必填只有一项**：`repo_url`；填了它，`owner` / `repo_name` / `owner_lower` 都会自动推导。反过来填了 `owner` + `repo_name`，`repo_url` 也会自动拼出来。

自动推导的字段（不用手填）：

| 派生字段 | 来源 |
|---|---|
| `owner_lower` | `owner` 小写，用于 `https://<owner>.github.io/<repo>/` |
| `repo_lower` | `repo_name` 小写 |
| `site_host` | `site_url` 的域名部分，用于 README 在线徽章 |
| `project` | 缺省时退回 `repo_name` |

## 顶层

| 字段 | 类型 | 说明 |
|---|---|---|
| `project` | string | 项目名，出现在标题、导航、页脚 |
| `tagline` | string | 一句话定位，用于 `<title>` 与 OG |
| `chip` | string | 首屏小徽章文案，如 `2026 · v0.1.0` |
| `title_main` | string | 大标题第一行（普通色） |
| `title_sub` | string | 大标题第二行（渐变色） |
| `lead` | string | 标题下的引导段，2 句内 |
| `desc` | string | SEO / 社交卡片描述 |
| `repo_url` | string | 仓库地址，所有 GitHub 按钮指向它 |
| `site_url` | string | 线上介绍页地址；留空则隐藏相关按钮与 canonical |
| `owner` | string | 仓库 owner，用于 README 徽章 |
| `repo_name` | string | 仓库名，用于 README 徽章 |
| `site_host` | string | 域名简称，用于 README 在线徽章 |
| `license` | string | 许可名，如 `MIT` |
| `intro` | string | README「这是什么」正文 |
| `usage` | string | README「使用说明」正文 |
| `tree` | string | README 项目结构树的正文（每行含 `├──`） |
| `license` | string | 已在上方 |
| `footer_note` | string | 页脚一句题记 |

## 区块文案

| 字段 | 说明 |
|---|---|
| `features_title` / `features_desc` | 特性区标题与副标题 |
| `start_title` / `start_desc` | 快速开始区 |
| `spec_title` / `spec_desc` | 规格区 |
| `limits_title` / `limits_desc` | 限制区 |
| `final_title` / `final_desc` | 底部 CTA 区 |

## 列表字段

### `stats`（首屏数字，3–4 条）

```json
{ "value": "124", "unit": "M", "label": "参数量" }
```

`value` 与 `unit` 分别渲染成主数字与高亮单位。

### `features`（特性卡，3–6 条）

```json
{ "icon": "◍", "title": "标题", "desc": "网页版描述（可含行内强调）", "desc_plain": "README 用纯文本版" }
```

`icon` 用单个字符或 emoji，别放图片。`desc` 用于 HTML（会被转义，写纯文本即可），`desc_plain` 用于 README 表格（不能含 `|`）。

### `steps`（快速开始步骤）

```json
{ "n": "1", "title": "准备环境", "code": "命令行文本\n可多行", "code_plain": "同上，README 用", "note": "补充说明" }
```

`code` 会放进 `<pre>` 风格的块里，注意 `<` `>` 会被转义，别指望 HTML 生效。

### `specs`（规格表）

```json
{ "k": "运行时", "v": "Node 18+" }
```

### `limits`（限制卡，2–4 条）

```json
{ "title": "不做 X", "desc": "为什么，替代方案是什么" }
```

### `term_lines`（终端演示）

```json
{ "cls": "c", "text": "$ npm run dev" }
```

`cls` 取值：

| cls | 效果 |
|---|---|
| `c` | 高亮青色（命令、提示符） |
| `m` | 暗灰（日志、耗时） |
| `p` | 紫蓝（输出主体） |
| `""` | 普通正文色 |

## 渲染命令

```bash
python scripts/render.py --template assets/landing.template.html --config site.json --out index.html
python scripts/render.py --template assets/readme.template.md --config site.json --out README.md --no-escape
```

`--no-escape` 只在生成 Markdown 时用，否则 `>` `<` `&` 会被转义成实体。
