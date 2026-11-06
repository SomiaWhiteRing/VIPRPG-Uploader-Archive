# VIPRPG アップローダー保存庫

uploader.jp / getuploader.com で公開された VIPRPG のゲーム・素材と投稿情報を、アップローダー名と投稿番号に沿って保存・整理するプロジェクトです。元の作品名・ファイル名・コメント・投稿日時を保っています。

[閲覧サイト][site] · [GitHub Pages ミラー][mirror] · [Internet Archive][ia] · [補完アーカイブ][release]

元の URL のドメインを `uploader.viprpg.org` に置き換えると、対応するページを開けます。分類は [VIPRPG 関連アップローダー一覧（Neocities）][directory] をもとにしています。

## 構成

Next.js と React で構造化 JSON を共通テンプレートに組み込み、静的サイトとして Cloudflare から配信します。本リポジトリはサイトと収録情報を管理し、保存ファイルは Internet Archive と GitHub Releases で提供しています。

- `src/data/`：`catalog.json` はファイル索引、`archive.json` は元ページ情報、`original-titles.json` は元ページのタイトル、`directory*.json` は分類。補完ファイルや保存状態の対応表もここに置きます。
- `src/lib/`：索引・補完データの統合と表示用データの組み立て。
- `src/components/`：共通の表示テンプレート。
- `public/vendor/uploader/`：元サイト由来の CSS と素材。
- `scripts/`：保存済み資料から表示用 JSON を生成する取り込み処理。

## 開発と確認

CI と同じ Node.js 24 を使用します。

```sh
npm ci
npm run dev
```

変更後の確認と静的出力：

```sh
npm run lint
npm run typecheck
npm run build
```

出力先は `out/` です。

## データ更新

元ページの取得と整理はローカルで行い、生成した `src/data/` の JSON を Git で管理します。基本スナップショットの書き出しには、保存元ディレクトリを指定します。

```text
python -X utf8 -B scripts/sync_catalog.py --root <rescue-root>
node scripts/import_archive.mjs <rescue-root>
```

`<rescue-root>` はローカル保存元のパスです。書き出し後に追加収録分の統合処理を行い、補完ファイル・保存状態・別名の対応表を含めて確認し、JSON をコミットします。サイトのビルドは、これらの JSON とテンプレートを読み込みます。

IA のダウンロード先は `ia-storage.json` と `ia-downloads.json` で管理します。`python -X utf8 -B scripts/sync_ia_downloads.py --plan <ia-migration-plan.json>` で全量の移行計画から生成します。元の保存状態と別に管理し、IA の公開インデックスへの反映を公開条件にせず、移行先の全ファイルが匿名でダウンロードできることを確認してからサイトを公開します。

後から保存したダウンロード詳細ページは、`node scripts/import_archive.mjs --missing-details <rescue-root> [<rescue-root> ...]` で未収録分のみを取り込めます。既存の詳細・アップローダー紹介・一覧は保持されます。

## デプロイ

`main` への push、または `.github/workflows/deploy.yml` の手動実行で、検査・ビルド・Cloudflare への配信を行います。配信設定は `wrangler.jsonc`、必要なリポジトリ Secret は `CLOUDFLARE_API_TOKEN` です。GitHub Pages ミラーも `.github/workflows/pages.yml` で独立してビルド・配信します。

# VIPRPG 上传区保存库

本项目按上传区名称与投稿编号，保存并整理 uploader.jp / getuploader.com 上公开的 VIPRPG 游戏、素材及投稿信息，保留原作品名、文件名、评论和投稿时间。

[浏览网站][site] · [GitHub Pages 镜像][mirror] · [Internet Archive][ia] · [补充存档][release]

将原地址的域名替换为 `uploader.viprpg.org`，即可打开对应页面。分类参考 [VIPRPG 相关上传区目录（Neocities）][directory]。

## 项目结构

网站使用 Next.js 和 React，将结构化 JSON 与共用模板生成静态页面，由 Cloudflare 提供访问。本仓库维护网站及收录信息，文件由 Internet Archive 和 GitHub Releases 提供。

- `src/data/`：`catalog.json` 保存文件索引，`archive.json` 保存原页面信息，`original-titles.json` 保存原页面标题，`directory*.json` 保存分类；补充文件和保存状态的映射也放在这里。
- `src/lib/`：合并索引与补充数据，组织页面使用的数据。
- `src/components/`：共用页面模板。
- `public/vendor/uploader/`：源站 CSS 和素材。
- `scripts/`：从已保存资料生成展示用 JSON 的导入脚本。

## 开发与检查

使用与 CI 一致的 Node.js 24。

```sh
npm ci
npm run dev
```

修改后的检查与静态构建：

```sh
npm run lint
npm run typecheck
npm run build
```

构建输出位于 `out/`。

## 数据更新

在本地抓取、整理原始页面，将生成的 `src/data/` JSON 纳入 Git。导出基础快照时，指定本地保存目录：

```text
python -X utf8 -B scripts/sync_catalog.py --root <rescue-root>
node scripts/import_archive.mjs <rescue-root>
```

`<rescue-root>` 为本地保存目录路径。导出后执行追加收录批次的合并流程，连同补充文件、保存状态和别名映射一起检查，再提交 JSON。网站构建读取这些 JSON 与模板。

上传区原件的拉取、检测、分流、上传和验收步骤见 [上传区资料整理流程](docs/uploader-ingest-workflow.md)。

检查已收录上传区的新投稿和列表变动，使用 [可复用更新扫描器](docs/uploader-update-scan.md)。默认只查最新页，没有更新就停止；另支持手动完整分页复查及本地快照比较。

IA 下载位置由 `ia-storage.json` 和 `ia-downloads.json` 管理。使用 `python -X utf8 -B scripts/sync_ia_downloads.py --plan <ia-migration-plan.json>` 从全量迁移计划生成，与原保存账本状态分开。IA 公开索引状态不作为网站发布条件；切换归档前确认目标文件全部可匿名下载，再统一发布网站。

后续保存的下载详情页可用 `node scripts/import_archive.mjs --missing-details <rescue-root> [<rescue-root> ...]` 仅补入遗漏，保留已有详情、上传区介绍和目录。

## 部署

推送 `main`，或手动运行 `.github/workflows/deploy.yml`，即可执行检查、构建并发布到 Cloudflare。部署配置位于 `wrangler.jsonc`，仓库需要设置 `CLOUDFLARE_API_TOKEN` Secret。GitHub Pages 镜像通过 `.github/workflows/pages.yml` 独立构建和发布。

[site]: https://uploader.viprpg.org/
[mirror]: https://somiawhitering.github.io/VIPRPG-Uploader-Archive/
[ia]: https://archive.org/details/VIPRPG-uploader-Archive-v2
[release]: https://github.com/SomiaWhiteRing/VIPRPG-Uploader-Archive/releases/latest
[directory]: https://viprpg.neocities.org/contents/uploader
