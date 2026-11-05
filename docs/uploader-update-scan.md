# 上传区更新扫描

扫描 `src/data/catalog.json` 收录的公开上传区，与网站索引和上次扫描快照比较。默认只看最新页：最新页没有变化就停止该区检查，不因总数变化翻旧页。只有最新页全是未收录投稿时，才继续往后读，遇到已收录记录就停。

按 `src/data/directory.json` 的分类跳过“本串拾遗”及其子分类中的全部上传区，不请求也不计入扫描结果；显式指定 `--uploader` 或使用 `--full` 时同样适用。分类增减会自动生效，报告记录跳过数量及名单。

只读取元数据，不下载作品原包，也不修改网站数据。`anime` 按原目录范围仅检查 56 号文件。环境需要 Python 3、`requests` 和 `beautifulsoup4`，无需启动网站。

以下配置路径是批次示例。运行时替换为实际在用的配置，并确认代理进程已启动。

```powershell
# 读取当前收录批次的代理和已有频率。
$scanSettings = Get-Content "D:/VIPRPG-Rescue/uploaderjp-202611/increments/scanned-uploaders-20261106/source/settings.json" -Raw | ConvertFrom-Json
python -X utf8 -B scripts/scan_uploader_updates.py --proxy $scanSettings.proxy_url --interval $scanSettings.request_interval_seconds --timeout $scanSettings.read_timeout_seconds

# 仅重查指定上传区；可以多次指定 --uploader。
python -X utf8 -B scripts/scan_uploader_updates.py --uploader vipkohaku2025 --proxy $scanSettings.proxy_url

# 仅在明确需要核对全部旧页时使用。
python -X utf8 -B scripts/scan_uploader_updates.py --full --proxy $scanSettings.proxy_url
```

## 请求频率

默认值与现有 `VIPRPG-Archive/scripts/uploader_rescue.py` 及 `D:/VIPRPG-Rescue/uploaderjp-202611/settings.json` 对齐：串行、请求起点至少间隔 1 秒、连接超时 15 秒、读取超时 45 秒，连接错误、超时、响应传输中断和 HTTP 5xx 按 10、30、90 秒退避。重定向和年龄确认请求同样遵守间隔。403、429 或访问挑战会停止整轮后续请求，并把未取得结果的上传区记为未核实。

代理地址以当前收录批次的 settings.json 为准，其他环境按实际路径填写。本次扫描曾使用批次的 127.0.0.1:18006 日本出口，未修改该批次的代理配置；临时代理结束后需使用当前实际运行的地址。不传 `--proxy` 时使用环境代理。可用 `--workers`、`--interval` 和 `--timeout` 覆盖设置；间隔在所有任务间共用。

2026-11-06 首轮使用 4 并发、未限速，随后源站返回 Cloudflare Error 1006，明确封禁出口 IP；具体触发阈值未知。按项目已有频率调整后，旧出口首个请求仍返回封禁，其余请求已停止。随后复用本项目现有收录批次正在使用的日本出口继续检查；读取地区已验证为 JP。

## 最新页比较

首页的投稿编号、名称、评论、原名、容量和日期参与比较；下载次数、广告和 HTML 变化不触发翻页。首次运行与网站保存的首页对比，之后与成功快照对比。当前文件总数单独记录，不作为访问旧页的条件。

普通扫描只报告本次观察到的未收录投稿和字段变化，不把没有访问的旧页视为已核实，不据此报告旧投稿消失。即使首页更新，只要这一页出现已收录记录，就不再往后翻。

`--full` 才会读取全部分页，并核对实际收集条数与源站声明总数。普通扫描保留前次完整扫描的时间 `fullAt`；未做过完整扫描时该值为 null。旧页静默编辑和同名同容量的原包内容替换不在普通扫描的检查范围内，后者也不能仅靠列表元数据判断。

每个完成的上传区立即保存快照。失败区保留旧快照，本次仍明确记为未核实。中断后再次运行依然先检查最新页。

## 结果和证据

默认输出在 Git 忽略的 `local/uploader-update-scan/`；可用 `--output <目录>` 指定其他位置。

- `latest.json`：最新报告路径和总计。
- `state.json`：每区最近成功快照，用于下次增量比较。
- `<UTC时间>/report.md`、`report.json`：报告、逐区结果和实际请求频率设置。
- `<UTC时间>/catalog-baseline.json`：启动时冻结的目录和比对字段。
- `<UTC时间>/pages/<上传区>/`：原始 HTML 和请求时间、URL、HTTP 状态回执。
- `<UTC时间>/progress.json`：运行进度及已完成结果。

`liveCount` 是源站声明总数，`observedCount` 是本次实际读取的记录数。报告区分未收录投稿、列表字段差异和未核实；仅完整扫描会列出源站当前未列出的历史记录。已有快照时，JSON 的 `sincePreviousScan` 记录本次观察范围内相对上次的变化，普通扫描不推断删除。

全部指定上传区成功返回退出码 0；有未核实区返回 1，但仍保存成功结果与报告。发现更新后，下载、检测、收录按 [上传区资料整理流程](uploader-ingest-workflow.md) 单独进行。
