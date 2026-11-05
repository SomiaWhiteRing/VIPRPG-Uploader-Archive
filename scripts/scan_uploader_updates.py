"""Read public uploader metadata, compare with the catalog, and retain reusable snapshots."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from threading import Event, Lock
import time
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
# The directory explicitly links only this file, not the entire unrelated uploader.
SCOPED_IDS = {"anime": ["56"]}
FIELDS = ("displayName", "comment", "name", "listedSize", "date")


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def skipped_uploaders(directory):
    skipped = set()
    pending = [(section, False) for section in directory]
    while pending:
        section, skip = pending.pop()
        skip = skip or section["zh"] == "本串拾遗"
        if skip:
            skipped.update(section.get("slugs", []))
        pending.extend((child, skip) for child in section.get("children", []))
    return skipped


class SourceError(Exception):
    pass


class RequestGate:
    def __init__(self, interval):
        self.interval = interval
        self.next_at = 0
        self.lock = Lock()
        self.blocked = Event()

    def wait(self):
        with self.lock:
            if self.blocked.is_set():
                raise SourceError("Not requested: source blocked this run; stopped further requests")
            time.sleep(max(0, self.next_at - time.monotonic()))
            if self.blocked.is_set():
                raise SourceError("Not requested: source blocked this run; stopped further requests")
            self.next_at = time.monotonic() + self.interval


class Reader:
    def __init__(self, directory, proxy, timeout, gate):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0 VIPRPG-local-preservation/1.0"
        if proxy:
            self.session.trust_env = False
            self.session.proxies = {"http": proxy, "https": proxy}
        self.timeout = timeout
        self.gate = gate
        self.requests = 0

    def page(self, url, label):
        method, data = "GET", None
        for gate in range(10):
            for attempt in range(4):
                self.gate.wait()
                self.requests += 1
                stem = self.directory / f"{label}-{gate}-{attempt}"
                try:
                    response = self.session.request(method, url, data=data,
                                                    timeout=(15, self.timeout), allow_redirects=False)
                except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError) as exc:
                    write_json(stem.with_suffix(".json"), {
                        "at": now(), "requestedUrl": url, "method": method, "error": str(exc),
                    })
                    if attempt == 3:
                        raise
                    time.sleep((10, 30, 90)[attempt])
                    continue
                stem.with_suffix(".html").write_bytes(response.content)
                write_json(stem.with_suffix(".json"), {
                    "at": now(), "requestedUrl": url, "responseUrl": response.url,
                    "status": response.status_code, "method": method,
                    "bytes": len(response.content),
                })
                if response.status_code not in (500, 502, 503, 504) or attempt == 3:
                    break
                time.sleep((10, 30, 90)[attempt])
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(response.url, response.headers.get("Location", ""))
                if response.status_code == 303 or (response.status_code in (301, 302) and method == "POST"):
                    method, data = "GET", None
                continue
            soup = BeautifulSoup(response.content, "html.parser")
            title = soup.title.get_text(strip=True) if soup.title else ""
            if response.status_code in (403, 429) or "Just a moment" in title:
                self.gate.blocked.set()
                raise SourceError(f"HTTP {response.status_code}: {title}; stopped further requests")
            if response.status_code != 200:
                raise SourceError(f"HTTP {response.status_code}: {title}")
            form = next((f for f in soup.select("form") if
                         f.get("method", "").lower() == "post"
                         and f.select_one('input[name=q][type=hidden]')
                         and not f.select_one('input[type=password]')), None)
            if form is None:
                return soup, response.url
            url = urljoin(response.url, form.get("action") or response.url)
            method = "POST"
            data = {i["name"]: i.get("value", "") for i in form.select("input[name]")}
        raise SourceError("Redirect or age confirmation loop did not yield source metadata")

    def close(self):
        self.session.close()


def listing(soup, url, slug, page):
    total = None
    for row in soup.select("table tr"):
        th, td = row.find("th"), row.find("td")
        if th and td and clean(th.get_text()) == "ファイル":
            match = re.match(r"([\d,]+)\s*ファイル", clean(td.get_text()))
            if match:
                total = int(match[1].replace(",", ""))
    rows = {}
    for row in soup.select("table tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 5:
            continue
        anchor = cells[0].select_one("a[href]")
        if anchor is None:
            continue
        source = urljoin(url, anchor["href"])
        match = re.fullmatch(r"/" + re.escape(slug) + r"/download/(\d+)/?", urlsplit(source).path)
        if not match:
            continue
        values = [clean(cell.get_text()) for cell in cells[:5]]
        rows[match[1]] = dict(zip(FIELDS, values), sourceUrl=source)
    if total is None or (not rows and total != 0):
        raise SourceError("Listing missing file statistic or file rows (password, error, or changed layout)")
    numbers = [int(a.get_text(strip=True)) for a in soup.select(".pagination a")
               if a.get_text(strip=True).isdecimal()]
    next_url = None
    anchor = soup.select_one(".pagination .next a[href]")
    if anchor:
        candidate = urljoin(url, anchor["href"])
        match = re.fullmatch(r"/" + re.escape(slug) + r"/index/date/desc/(\d+)/?", urlsplit(candidate).path)
        if match and int(match[1]) == page + 1 and int(match[1]) <= max(numbers, default=page):
            next_url = candidate
    return total, rows, next_url


def scan_group(group, old, catalog_rows, catalog_head, args, run, gate):
    slug = group["slug"]
    reader = Reader(run / "pages" / slug, args.proxy, args.timeout, gate)
    started = time.monotonic()
    try:
        if slug in SCOPED_IDS:
            rows = {}
            for fid in SCOPED_IDS[slug]:
                url = group["sourceUrl"].rstrip("/") + "/download/" + fid
                soup, actual = reader.page(url, "detail-" + fid)
                fields = {}
                for row in soup.select("table tr"):
                    th, td = row.find("th"), row.find("td")
                    if th and td:
                        fields[clean(th.get_text())] = clean(td.get_text())
                if not fields.get("ファイル") or not fields.get("日時"):
                    raise SourceError("Scoped detail not available")
                date = fields["日時"]
                rows[fid] = {
                    "displayName": fields["ファイル"], "comment": fields.get("コメント", ""),
                    "name": fields.get("オリジナル") or fields["ファイル"],
                    "listedSize": fields.get("容量", ""),
                    "date": datetime.strptime(date, "%Y/%m/%d %H:%M:%S").strftime("%y/%m/%d %H:%M"),
                    "sourceUrl": actual,
                }
            snapshot = {"checkedAt": now(), "fullAt": now(), "total": len(rows), "rows": rows,
                        "head": rows, "scope": "explicit-file-ids"}
            return {"slug": slug, "status": "full", "snapshot": snapshot,
                    "pages": len(rows), "requests": reader.requests}
        soup, actual = reader.page(group["sourceUrl"], "page-1")
        total, rows, next_url = listing(soup, actual, slug, 1)
        head = rows.copy()
        # A normal scan reads only the latest page, extending through entirely new pages if needed.
        previous_head = old["head"] if old else catalog_head
        head_changed = previous_head.keys() != head.keys() or bool(differences(previous_head, head))
        page = 1
        if not args.full:
            while head_changed and next_url and rows and not (rows.keys() & catalog_rows.keys()):
                page += 1
                soup, actual = reader.page(next_url, f"page-{page}")
                page_total, page_rows, next_url = listing(soup, actual, slug, page)
                if page_total != total or rows.keys() & page_rows.keys():
                    raise SourceError("Listing changed during pagination; rerun this uploader")
                rows.update(page_rows)
            return {"slug": slug, "status": "quick", "pages": page, "requests": reader.requests,
                    "headChanged": head_changed, "snapshot": {
                        "checkedAt": now(), "fullAt": old.get("fullAt") if old else None,
                        "total": total, "rows": {**(old["rows"] if old else catalog_rows), **rows},
                        "observed": rows, "head": head, "scope": "latest-pages"}}
        while next_url:
            page += 1
            soup, actual = reader.page(next_url, f"page-{page}")
            page_total, page_rows, next_url = listing(soup, actual, slug, page)
            if page_total != total or rows.keys() & page_rows.keys():
                raise SourceError("Listing changed during pagination; rerun this uploader")
            rows.update(page_rows)
        if len(rows) != total:
            raise SourceError(f"Incomplete pagination: collected {len(rows)} of {total}")
        return {"slug": slug, "status": "full", "pages": page, "requests": reader.requests,
                "snapshot": {"checkedAt": now(), "fullAt": now(), "total": total,
                             "rows": rows, "head": head, "scope": "uploader"}}
    except (requests.RequestException, SourceError, ValueError) as exc:
        return {"slug": slug, "status": "unverified", "error": str(exc), "requests": reader.requests}
    finally:
        reader.close()
        elapsed = round(time.monotonic() - started, 1)
        if reader.requests:
            print(f"{slug}: {reader.requests} requests, {elapsed}s", flush=True)


def differences(before, after):
    changed = []
    for fid in sorted(before.keys() & after.keys(), key=int):
        fields = {}
        for field in FIELDS:
            a, b = before[fid][field], after[fid][field]
            if a == b or (field != "comment" and not a):
                continue
            # Some saved records have full detail comments; listings append or truncate with "...".
            if field == "comment" and b.endswith("...") and a.startswith(b[:-3]):
                continue
            fields[field] = {"before": a, "after": b}
        if fields:
            changed.append({"id": fid, "changes": fields})
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Read every page, including old metadata edits")
    parser.add_argument("--proxy", help="Explicit HTTP proxy; otherwise use environment proxies")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--interval", type=float, default=1.0, help="Minimum seconds between requests globally")
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--output", type=Path, default=ROOT / "local/uploader-update-scan")
    parser.add_argument("--uploader", action="append", help="Limit to a slug; may be repeated")
    args = parser.parse_args()
    if args.workers < 1 or args.timeout <= 0 or args.interval < 0:
        parser.error("workers and timeout must be positive; interval must be nonnegative")
    catalog = json.loads((ROOT / "src/data/catalog.json").read_text(encoding="utf-8"))
    archive = json.loads((ROOT / "src/data/archive.json").read_text(encoding="utf-8"))
    groups = [g for g in catalog["groups"] if not args.uploader or g["slug"] in args.uploader]
    if args.uploader and set(args.uploader) - {g["slug"] for g in groups}:
        parser.error("Unknown uploader slug")
    directory = json.loads((ROOT / "src/data/directory.json").read_text(encoding="utf-8"))
    skipped = skipped_uploaders(directory)
    skipped_groups = sorted(g["slug"] for g in groups if g["slug"] in skipped)
    groups = [g for g in groups if g["slug"] not in skipped]
    baseline = {}
    for file in catalog["files"]:
        details = archive["files"].get(f'{file["uploader"]}/{file["id"]}', {})
        date = clean(file.get("date") or details.get("fullDate"))
        if re.fullmatch(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}", date):
            date = date[2:16]
        baseline.setdefault(file["uploader"], {})[file["id"]] = {
            "name": clean(details.get("original") or file["name"]), "displayName": clean(details.get("displayName", file["name"])),
            "comment": clean(details.get("listComment", details.get("comment", ""))),
            "listedSize": clean(details.get("listedSize") or file.get("listedSize")), "date": date,
            "sourceUrl": file["sourceUrl"],
        }
    args.output = args.output.resolve()
    state_path = args.output / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"version": 1, "groups": {}}
    started = now()
    run = args.output / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run.mkdir(parents=True)
    write_json(run / "catalog-baseline.json", {"updatedAt": catalog["updatedAt"],
               "groups": [g["slug"] for g in groups], "files": baseline})
    results = []
    gate = RequestGate(args.interval)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(
            scan_group, g, state["groups"].get(g["slug"]), baseline.get(g["slug"], {}),
            {fid: baseline[g["slug"]][fid] for fid in archive["listings"].get(f'/{g["slug"]}', {}).get("ids", [])
             if fid in baseline.get(g["slug"], {})}, args, run, gate) for g in groups]
        for future in as_completed(futures):
            result = future.result()
            slug = result["slug"]
            if result["status"] != "unverified":
                snapshot = result.pop("snapshot")
                live, local = snapshot.get("observed", snapshot["rows"]), baseline.get(slug, {})
                result.update({"liveCount": snapshot["total"], "observedCount": len(live), "catalogCount": len(local),
                               "checkedAt": snapshot["checkedAt"], "fullAt": snapshot["fullAt"],
                               "newToCatalog": [{"id": fid, **live[fid]} for fid in sorted(live.keys() - local.keys(), key=int)],
                               "notListedAtSource": sorted(local.keys() - live.keys(), key=int) if result["status"] == "full" else [],
                               "metadataChanges": differences(local, live)})
                old = state["groups"].get(slug)
                if old:
                    previous = old["rows"]
                    result["sincePreviousScan"] = {
                        "previousCheckedAt": old["checkedAt"],
                        "added": sorted(live.keys() - previous.keys(), key=int),
                        "removed": sorted(previous.keys() - live.keys(), key=int) if result["status"] == "full" else [],
                        "changed": differences(previous, live),
                    }
                state["groups"][slug] = snapshot
                write_json(state_path, state)
            results.append(result)
            write_json(run / "progress.json", {"startedAt": started, "finished": len(results), "total": len(groups), "results": results})
    results.sort(key=lambda r: r["slug"].lower())
    summary = {
        "groups": len(groups), "skippedGroups": len(skipped_groups),
        "full": sum(r["status"] == "full" for r in results),
        "quick": sum(r["status"] == "quick" for r in results),
        "unverified": sum(r["status"] == "unverified" for r in results),
        "requests": sum(r["requests"] for r in results), "pages": sum(r.get("pages", 0) for r in results),
        "newToCatalog": sum(len(r.get("newToCatalog", [])) for r in results),
        "notListedAtSource": sum(len(r.get("notListedAtSource", [])) for r in results),
        "metadataChanges": sum(len(r.get("metadataChanges", [])) for r in results),
    }
    report = {"startedAt": started, "completedAt": now(), "catalogUpdatedAt": catalog["updatedAt"],
              "mode": "full" if args.full else "latest-pages", "summary": summary, "results": results,
              "skipped": {"category": "本串拾遗", "uploaders": skipped_groups},
              "requestPolicy": {"workers": args.workers, "intervalSeconds": args.interval,
                                "readTimeoutSeconds": args.timeout, "retryDelaysSeconds": [10, 30, 90]}}
    write_json(run / "report.json", report)
    lines = ["# 上传区更新扫描", "", f"开始：{started}；结束：{report['completedAt']}", "",
             f"对照网站索引：{catalog['updatedAt']}。", "",
             f"范围 {summary['groups']} 个区；完整检查 {summary['full']}；快速检查 {summary['quick']}；未核实 {summary['unverified']}。",
             f"按目录分类跳过本串拾遗 {summary['skippedGroups']} 个区。",
             f"读取 {summary['pages']} 个元数据页面，HTTP 请求 {summary['requests']} 次。",
             f"未收录 {summary['newToCatalog']} 条；源站未列出 {summary['notListedAtSource']} 条；列表字段差异 {summary['metadataChanges']} 条。", "",
             "本次快速模式仅检查最新页；最新页未变就停止。仅最新页全是未收录记录时往后翻到已收录记录。旧页复核须用 --full。",
             "源站未列出表示当前列表与存档不同，首次扫描不能据此确定删除时间。列表字段差异不等于文件内容变化。",
             "anime 仅检查原目录明确收录的 56 号文件。原始响应与请求回执在本报告同目录 pages/ 下。", ""]
    for result in results:
        slug = result["slug"]
        if result["status"] == "unverified":
            lines.extend([f"## {slug}：未核实", "", result["error"], ""])
            continue
        if not any(result.get(k) for k in ("newToCatalog", "notListedAtSource", "metadataChanges")):
            continue
        lines.extend([f"## {slug}", ""])
        for row in result["newToCatalog"]:
            lines.append(f"- 未收录 [{row['id']}: {row['name']}]({row['sourceUrl']}) · {row['date']} · {row['listedSize']}")
        if result["notListedAtSource"]:
            lines.append("- 源站未列出：" + ", ".join(result["notListedAtSource"]))
        for change in result["metadataChanges"]:
            lines.append(f"- {change['id']} 字段差异：" + json.dumps(change["changes"], ensure_ascii=False))
        lines.append("")
    (run / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(args.output / "latest.json", {"report": str(run / "report.json"), "markdown": str(run / "report.md"), "summary": summary})
    print(json.dumps({"report": str(run / "report.md"), **summary}, ensure_ascii=False), flush=True)
    return 1 if summary["unverified"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
