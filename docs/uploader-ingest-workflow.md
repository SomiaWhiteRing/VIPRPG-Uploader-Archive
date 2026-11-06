# 上传区资料的拉取、检测与分流流程

本文面向需要从头整理 uploader.jp / getuploader.com 公开资料的维护者。一次批次以投稿记录为单位，经过来源保存、文件检测、存储分流、公开验收与网站更新，形成可接续的证据链。本文以 2026 年 11 月 tkoolwatch 三个目录的批次为实例；每次开始时，以当前用户授权、目标服务和实际工作环境为准。

## 1. 建立批次

1. 确定目录、投稿编号、网站分类、存储目标、检测范围和完成条件。将每条记录的上传区名、投稿编号、列表页与详情页地址、原始标题和文件名写入批次清单，按 `上传区/投稿编号` 建立唯一键。
2. 保存列表页和详情页原文及抓取时间，记录编码、分页和来源地址。用现有网站索引逐项比对，形成已收录、待补充和需要复核的清单；后续工作以冻结清单为范围。
3. 为批次建立独立工作目录 `W`，记录授权、目标、清单、网络出口、状态、事件、传输回执和 SQLite 账本。源数据目录记为 `R`，网站仓库记为 `SITE`。变更前使用 SQLite 在线备份和文件副本保留原状态。
4. 确认现有 Internet Archive 条目、GitHub 仓库和唯一补充 Release。记录条目标识、Release tag、资产列表及对应链接。例次目标分别是 `VIPRPG-uploaderjp-Archive` 与 `vt-supplement-2026-10-28`；执行时重新核对实际目标。
5. 配置 Python、7-Zip、Internet Archive 客户端、GitHub CLI、MIDI 解析库与本地杀毒工具。源站、VT 和 IA 使用经过授权并实际验证地区的网络出口。例次使用 `127.0.0.1:7897` 的日本出口；每次启动写入工作前用匿名请求核对出口。

凭证保存在批次外的私有配置中。VT 密钥、IA 凭证与 GitHub 凭证按对应服务逐请求使用；公开 XML、公开文件读回和地区探测使用匿名会话。状态、日志和文档记录路径与结果，凭证值保留在私有环境。

## 2. 目录与账本

例次根目录为 `D:/VIPRPG-Rescue/uploaderjp-202611`，批次目录为该根目录下的 `increments/tkoolwatch-278-20261102`。三个目录冻结了 278 条新增记录，网站分类为「他」。下表中的文件为各阶段的工作依据。

| 路径 | 内容与用途 |
| --- | --- |
| `W/authorization.json`、`W/contract.json`、`W/scope.csv` | 授权、冻结范围、目标和来源映射 |
| `W/source/queue.sqlite`、`W/source/status.json` | 来源下载账本与运行状态 |
| `W/source/files/<上传区>/<编号>/` | 来源文件、传输回执与保留的原始响应 |
| `W/routing.sqlite`、`W/state.json`、`W/history.jsonl` | 批次准入、分流状态与进度历史 |
| `W/malware-audit/review.sqlite`、`W/malware-audit/packages/` | 文件成员清单、程序指纹、脚本审查和检测结果 |
| `W/vt/` | VT 样本指纹、查询记录、分析 ID 与报告回执 |
| `W/midi-local-check-20261102/` | MIDI 本地杀毒、结构检查和来源关联 |
| `W/ia/queue.sqlite`、`W/ia/events.jsonl` | IA 请求、接收与公开验收记录 |
| `W/release/queue.sqlite`、`W/release/events.jsonl` | Release 资产、清单与公开验收记录 |
| `W/website-checkpoints/`、`W/website-validation.json` | 网站数据备份和检查结果 |

运行中的事件、响应回执、样本分析 ID 和请求尝试均随账本保存。使用 `PRAGMA quick_check` 检查 SQLite，并在重要边界记录快照。磁盘空间按批次需要预留；例次要求 C、D 盘各至少 80 GiB。

## 3. 拉取与来源核对

1. 将冻结清单导入来源账本。按详情页保存投稿信息、原始文件名、时间、文件大小、来源 MD5 和密码状态。
2. 使用经过地区验证的出口串行拉取原件。为每条请求记录 URL、时间、HTTP 结果、内容长度、来源 MD5、实际 MD5 和文件路径；续传使用已有传输回执与 `.part` 文件衔接。
3. 将响应长度、实际长度和来源 MD5 对齐；取得来源原件后保留其字节和原始文件名。源站要求密码时，保留来源页及密码状态，后续按实际取得的原件推进。
4. 源站返回 0 字节时，保存响应及复核依据，按网站已有 `damaged-files.json` 标记文件损坏。文件与来源 MD5 一致时，按来源原件登记；文件格式检查与来源身份分别记录。
5. 复查状态、清单数量和传输记录。取得文件进入检测；来源密码或损坏记录进入网站及批次清单，保留对应证据。

例次 `W/download-scoped.py` 使用固定范围和 `C:/Users/旻/Documents/GitHub/VIPRPG-Archive/scripts/uploader_rescue.py` 下载器；其 278 条断言与 `R` 路径属于该批专用配置。新批次根据自身清单和路径建立对应入口。下载器的 `files`、`pages`、`runs`、`events` 表分别记录文件、页面、运行和事件；进程与暂停标记由同一批次的状态文件协调。

## 4. 文件清点和检测

### 4.1 静态清点

对取得的原包保留原件，逐层读取可检查的归档成员，记录成员路径、长度、MD5、格式、加密状态和来源键。清点结果连接到原包，便于同一指纹在多个作品中复用报告。记录检查覆盖范围，并为需要进一步审查的成员保留依据。

程序类检测范围包括 `.exe`、`.dll`、`.scr`、`.com`、`.ocx`、`.cpl`、`.msi` 和带 `MZ` 头的文件。脚本按现有静态审查门禁处理；可以通过逐字节比对已发布的对应版本、检查内容与保存来源证据形成审查结论。程序和脚本清点均在静态读取环境中进行。

密码保护原包及包含 RGSSAD 等加密资源的已取得原包，保留原始字节及加密证据，分流至现有补充 Release。归档结构的可读取范围单独记录，后续检测按实际覆盖推进。

### 4.2 程序文件的 VirusTotal 检查

1. 按 MD5 对程序类成员去重，建立指纹到全部来源成员的映射。
2. 先在本地账本和 VT 查询同一 MD5 的既有报告。已完成的报告记录分析时间、`malicious`、`suspicious` 和引擎结果；零检出与有检出分别进入对应分流。
3. 需要新分析的成员，以实际授权提交样本，保存 HTTP 回执、分析 ID 和提交时间。依据分析 ID 回收结果，并将完成结果关联至 MD5 和来源成员。
4. 按全局 VT 锁、实际配额与每次请求的时间间隔安排查询和提交。例次使用至少 16 秒间隔；配额变化和临时网络情况以服务回执为准。对待确认的请求先核对已有报告、分析 ID 和历史回执，再决定下一步。

VT 检测结果适用于本次约定的程序类成员，检测范围、版本和实际报告一起归档。已完成样本的报告可按精确 MD5 复用。

VT v3 的对应接口为 `GET https://www.virustotal.com/api/v3/files/{MD5}`、`POST https://www.virustotal.com/api/v3/files` 和 `GET https://www.virustotal.com/api/v3/analyses/{analysis_id}`。按服务文档处理大文件上传地址；每次响应保存状态和时间，完成报告保存完整分析信息。

### 4.3 MIDI 的本地检查

对 `.mid`、`.midi`、`.rmi` 成员按 MD5 和长度去重，保留来源及成员路径。复用已有同指纹、同长度的本地杀毒结果；其余成员提取到批次样本目录，使用经签名核验的本地杀毒引擎扫描，并核对逐文件日志覆盖。例次使用 Emsisoft Commandline Scanner，记录引擎与病毒库日期，采用本地扫描配置。

同时使用 MIDI 解析器记录结构结果。结构检查与杀毒结果分别保存；每个结论均能追溯到指纹、原包和成员路径。例次的 `W/midi-local-check-20261102/inventory.json`、`summary.json` 与 `W/midi_gate.py` 展示了结果组织和门禁校验。

例次的离线扫描命令如下，`<样本目录>` 和 `<日志路径>` 使用当前批次的绝对路径。扫描前核对程序签名与病毒库日期，扫描后将日志中的每个样本路径与冻结指纹清单逐项对账。

```powershell
& "$R/private/local-midi-scan/emsisoft/a2cmd.exe" "/f=<样本目录>" /cloud=0 /logClean "/l=<日志路径>"
```

## 5. 分流与上传

| 条件 | 处理路径 | 进入下一阶段的依据 |
| --- | --- | --- |
| 程序成员 VT 零检出，MIDI 与静态门禁完成 | Internet Archive | 成员报告、本地 MIDI 结果、来源长度与 MD5 |
| 程序或已有原包报告出现检出 | 现有唯一 GitHub Release | 检测报告、原包身份与分流记录 |
| 已取得密码保护原包或含加密资源的原包 | 现有唯一 GitHub Release | 来源原件、长度、MD5 与加密证据 |
| 已取得且归档结构待复核的原包 | 现有唯一 GitHub Release | 来源原件、长度、MD5 与结构检查记录 |
| 来源密码或来源文件损坏 | 网站记录与批次清单 | 来源详情、响应或密码状态 |
| 检查覆盖或结果正在形成 | 待核队列 | 已有证据、具体待完成环节与复核时间 |

### 5.1 Internet Archive

- 按批次计划生成稳定的目标路径、文件级标题、来源长度与 MD5。检查目标条目的公开状态、容量和全局写入锁，保持授权范围内的单线程写入。
- 每项写入先持久化尝试，再保存 HTTP 状态、ETag、时间及平台任务。`accepted` 表示平台已接收；查询 Metadata API、公开文件 XML 和匿名完整 GET 后，路径、标题、长度及 MD5 均一致时记为 `indexed`。
- 已接收对象由公开验收步骤推进；请求结果待确认时，以响应、平台任务历史、Metadata API、XML 和公开读回共同确认对象状态。
- 批次原件完成公开验收后，生成各目录和总批次清单，记录来源键、原文件名、状态、MD5 与实际下载位置；清单同样保存接收回执并进行公开读回。三个目录和一份总批次对应四份清单，以实际计划中的四个路径逐项对账。

### 5.2 GitHub Release

- 查询目标仓库当前唯一补充 Release 的 ID、tag、资产列表和上传地址。为每个原包确定稳定的资产名称，核对来源文件长度和 MD5。
- 将原包追加到该 Release，保存资产 ID、上传响应、大小、下载地址与原包映射。已存在资产以名称、大小和完整下载 MD5 核对后复用。
- 使用匿名完整 GET 校验资产长度与 MD5，验收通过后更新批次映射，并生成带版本指纹的补充清单。原有资产与链接沿用各自已验证的位置。

## 6. 网站数据与检查

1. 将列表、详情、来源日期和上传区分类合并到 `SITE/src/data/`。`catalog.json` 管理索引与状态，`archive.json` 管理详情，`directory.json` 管理分类，`supplements.json` 关联 Release，`damaged-files.json` 记录来源损坏。
2. IA 下载位置由 `ia-storage.json` 与 `ia-downloads.json` 决定，用 `scripts/sync_ia_downloads.py --plan <全量迁移计划>` 生成；它们与保存账本中的 `indexed` 状态独立。对已确认可靠原件的 IA 服务器端迁移，沿用现有校验值，通过匿名 HEAD 与长度确认下载可用性，不重新下载原件计算指纹；目标文件全部可下载后再统一切换网站。Release 补充链接、密码状态和来源损坏沿用现有映射与展示方式。
3. 对照合并前快照检查既有目录、记录、链接与用户修改。保存本批同步记录及网站数据备份。
4. 在网站仓库执行已有静态检查，并保存退出码及检查时间：

```powershell
npm run lint
npm run typecheck
```

例次使用 `W/sync-site.py` 和 `W/sync-details.py` 根据本批账本同步数据。发布、推送与部署按照当次明确授权执行。

## 7. 调度、恢复与完成

批次任务发起后，使用一个既有的 30 分钟检查周期，依次读取来源、检测、IA、Release、网站和进程状态。正常排队和服务退避由工作进程续接；进程、暂停标记和已有回执共同决定后续操作。出现服务权限变化、用户需要提供的信息、关键恢复或全部完成时报告具体证据。

恢复时先核对实际命令行、父子进程、锁、SQLite 完整性、最新事件和状态时间。网络出口、权限、容量、磁盘空间与待处理请求的回执均符合当前批次条件后，从账本中最早待处理项接续。为状态或脚本调整保存一致性备份和原日志，并通过静态或临时检查核对改动。

完成验收以冻结清单逐项对账：每条记录有来源状态与去向；取得的原包具备检测依据和公开验收记录；来源密码和损坏项目保留事实；目录、详情、分类、补充映射及网站检查结果齐全。保存最终快照，确认各工作进程结束，然后关闭本批定时检查。

## 8. 例次入口与操作顺序

以下入口属于 tkoolwatch 278 项批次。它们包含该批目录、路径与范围配置；复用流程时先准备新批次的配置、账本、脚本和来源清单。

```powershell
$R = 'D:/VIPRPG-Rescue/uploaderjp-202611'
$W = "$R/increments/tkoolwatch-278-20261102"
$Python = 'C:/Users/旻/AppData/Local/Programs/Python/Python311/python.exe'
$IaPython = "$R/private/ia-venv/Scripts/python.exe"

# 按冻结来源清单取得原件，已有回执由账本衔接
& $Python -X utf8 -B "$W/download-scoped.py"

# 准入已取得来源并建立静态检测记录
& $Python -X utf8 -B "$W/refresh-state.py"
& $Python -X utf8 -B "$W/classify-ready.py"

# 录入本地 MIDI 和 VT 报告后，重新计算分流并扩展 IA 计划
& $Python -X utf8 -B "$W/classify-ready.py" --reconcile-only
& $Python -X utf8 -B "$W/ia/refresh-plan.py"

# 按账本上传并验收 IA 原件
& $IaPython -X utf8 -B "$W/upload-ia.py" upload
& $IaPython -X utf8 -B "$W/upload-ia.py" verify

# 按已核对的 Release 计划追加原件并完整读回
& $Python -X utf8 -B "$W/release/worker.py"

# 同步网站数据
& $Python -X utf8 -B "$W/sync-site.py"
& $Python -X utf8 -B "$W/sync-details.py"
```

每一步以本批授权、当前账本状态和前一步验收结果为启动条件。程序类 VT 的精确 MD5 查询、授权提交和分析结果回收分别保存回执；MIDI 使用本地检查；Release 资产按 `W/release/plan.json` 和 `W/release/worker.py` 的实际计划追加并验收。清单生成与验收依据批次的实际来源状态和清单数量配置，按计划中每个路径逐项检查接收回执、Metadata API、公开 XML 和完整 GET。各批次使用自己的记录、名称与目标，完成后将操作依据和最终快照一并保存。
