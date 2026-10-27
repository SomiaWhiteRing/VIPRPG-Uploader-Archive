# VIPRPG 上传区保存库

参考 VIPRPG-Archive：Next.js 静态导出到 `out/`，Cloudflare 只提供静态资源。目标域名为 `uploader.viprpg.org`，没有 Worker 脚本、API 或运行时数据库。

## 数据与模板分离

构建只读取清洗好的 JSON 与共用 React 模板，不访问原网站、不解析缓存 HTML，也不需要下载队列或本地恢复目录。

- `src/data/catalog.json`：上传区、文件编号、原地址、本地保存状态、IA 上传／公开状态及实际存储键。
- `src/data/archive.json`：上传区名称与说明、文件详情、列表原始顺序和分页关系。说明只允许文字、换行、链接、加粗及强调等结构化节点，不保存整页 HTML。
- `src/data/directory.json`：首页栏目及祭典分组。
- `src/data/directory-source.json`：Neocities 分类来源的公开 URL 和抓取时间。
- `src/components/uploader-view.tsx`、`file-view.tsx`、`file-table.tsx`：沿用源站 DOM 类名的共用模板。
- `public/vendor/uploader/`：原站使用的 Bootstrap 3.3.2、uploader.css、rwd-table 样式、图标字体及 favicon；来源见该目录的 README。

清单省略与 `catalog.json` 完全相同的名称、原文件名、容量，以及与完整评论相同的列表评论，由既有回退规则显示同样的值；导入脚本自动执行这一精简。构建端统一建立文件索引，列表和搜索页只向浏览器传递实际使用的字段，不携带 MD5、归档存储路径等详情数据。

183 个上传区、10,668 份文件详情和 824 份列表／分页记录已结构化。169 个文件没有有效详情快照，页面明确显示仅有索引信息。原作品名、评论、日期、原始下载次数与上传区说明保留原文，网页的操作与状态文字支持中日文。

原站 HTML、抓取记录、缺页报告、浏览器测试输出和构建产物属于本地开发资料，由 `.gitignore` 排除，不提交、不参与 GitHub Actions 构建。本地旧 HTML 证据仍保留，不因页面实现调整而改写或删除。

## 页面与链接

`/<上传区>/` 浏览原列表；`/<上传区>/download/<编号>` 查看文件；`/<上传区>/index/date/desc/<页码>` 保留原分页路径；`/<上传区>/search` 使用静态数据在浏览器内检索和排序。

将 `https://uu.getuploader.com/part4past/download/1` 的域名换成 `uploader.viprpg.org` 即可直达。保留上传区大小写。首页支持粘贴原 uploader 地址定位上传区或文件。

主页按 Neocities 原目录收纳：祭典置于最前，内部按具体祭典分组；本スレ用うｐろだ置于第二位，其余栏目维持原顺序。183 个上传区各出现一次。分类来源为 `https://viprpg.neocities.org/contents/uploader`，来源在底栏标注。

## 展示规则

导航显示当前语言对应的国旗并支持切换，语言与关闭归档说明的选择保存在浏览器 localStorage。首屏在语言就绪后显示，避免 Bootstrap 的子元素 visibility 覆盖；页面标题、description、Open Graph、Twitter 及界面提示随语言更新。初始化 title 只包含原文件名／上传区名与 VIPRPG，不先显示默认中文站名。禁用 JavaScript 时显示静态中文页面。

`PageMetadata` 通过 React 声明 title 和 meta，由单一组件管理其生命周期，不再与 Next.js 静态标题同时写入 `document.title`，避免生产环境初始化时相互覆盖。

列表、详情、搜索和分页使用原站通知样式说明数据是固定快照。已找到密码并保存成功的文件按普通文件呈现；未保存的密码文件显示真实保存状态，不再展示没有实际作用的密码认证入口。上传、编辑、管理、注册、举报、原站通知和推广等控件不进入模板。

只有 `indexed`（IA 公开元数据匹配长度与 MD5）提供归档下载；`accepted` 仅代表上传端接收，不能视为公开下载已就绪，也不声称逐文件回读通过。传输容器使用实际存储键并说明先解包取出原分卷。

## 本地数据准备

下列步骤独立于网站构建，仅在需要更新快照时手动执行：

```powershell
python -X utf8 -B scripts/sync_catalog.py --root D:/VIPRPG-Rescue/uploaderjp-202611
node scripts/import_archive.mjs D:/VIPRPG-Rescue/uploaderjp-202611
```

第一步只读上传账本并导出公开状态；第二步只读已保存的源页面，在入口提取和清洗结构化字段，导出 `archive.json`。它不上传文件、不执行原站脚本、不改动工作进程或队列。坏元数据与缺页清单保存在被忽略的 `local/reports/`。

导出后将 JSON 数据随代码提交；GitHub Actions 不运行导入步骤，也不依赖开发机器上的源页面缓存。

## 开发与部署

```text
npm ci
npm run lint
npm run typecheck
npm run dev -- --hostname 127.0.0.1 --port 3101
npm run build
```

`npm run build` 生成 `out/`。`wrangler.jsonc` 与 VIPRPG-Archive 一样采用 assets-only 配置和静态 HTML 路径处理，不执行 Worker 服务端代码。获得发布授权后，推送 `main` 或手动触发 `.github/workflows/deploy.yml`，由 GitHub Actions 校验、构建并部署；需要仓库 Secret `CLOUDFLARE_API_TOKEN`。不使用 Cloudflare Builds，不保存 Actions 构建产物或缓存。

`public/_headers` 保留原缓存策略并增加 `no-transform`，防止 Cloudflare 向静态 HTML 自动注入统计脚本而破坏 React 初始化。该设置只作用于本站静态资源，不更改其他站点配置。

无 JavaScript 的回退样式放在 `body` 的 `noscript` 内，原站 CSS 使用相同 `precedence` 保持加载顺序并由 React 管理资源，避免 `head` 的普通节点与 Cloudflare 全域 Google 标签注入发生 React 初始化冲突；不更改全域统计配置。
