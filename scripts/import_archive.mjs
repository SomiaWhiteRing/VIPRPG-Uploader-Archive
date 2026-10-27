// One-time/local data preparation. The website build reads only the resulting JSON.
import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import { load } from "cheerio";
import { compactArchive } from "./compact_archive.mjs";

const root = process.argv[2];
if (!root) throw new Error("Usage: node scripts/import_archive.mjs <rescue-root>");
const sourceDir = path.join(root, "source-pages");
const catalog = JSON.parse(fs.readFileSync("src/data/catalog.json", "utf8"));
const knownGroups = new Set(catalog.groups.map(group => group.slug));
const knownFiles = new Set(catalog.files.map(file => `${file.uploader}/${file.id}`));
const candidates = new Map();
const unreadable = [];
for (const name of fs.readdirSync(sourceDir)) {
  if (!name.endsWith(".json")) continue;
  let meta;
  try { meta = JSON.parse(fs.readFileSync(path.join(sourceDir, name), "utf8")); }
  catch { unreadable.push(name); continue; }
  if (meta.status !== 200 || !meta.content_type?.includes("text/html")) continue;
  const route = new URL(meta.requested_url).pathname.replace(/\/$/, "");
  const match = route.match(/^\/([^/]+)(?:\/download\/(\d+)|\/index\/date\/desc\/\d+)?$/);
  if (!match || !knownGroups.has(match[1]) || (match[2] && !knownFiles.has(`${match[1]}/${match[2]}`))) continue;
  const file = path.join(sourceDir, name.replace(/\.json$/, ".html"));
  if (!fs.existsSync(file)) continue;
  const entries = candidates.get(route) || [];
  entries.push({ meta, file });
  candidates.set(route, entries);
}

const archive = { uploaders: {}, files: {}, listings: {} };
const listFields = {};
function link(raw, base) {
  if (!raw || !URL.canParse(raw, base)) return null;
  const url = new URL(raw, base);
  if (!["http:", "https:", "mailto:"].includes(url.protocol)) return null;
  if (/(^|\.)getuploader\.com$/.test(url.hostname) && knownGroups.has(url.pathname.split("/")[1])) return `${url.pathname.replace(/\/$/, "")}${url.search}${url.hash}`;
  return url.href;
}
function rich(nodes, base) {
  return nodes.flatMap(node => {
    if (node.type === "text") return node.data ? [{ type: "text", text: node.data }] : [];
    if (node.type !== "tag" || ["script", "style", "iframe", "object", "embed"].includes(node.name)) return [];
    if (node.name === "br") return [{ type: "break" }];
    const children = rich(node.children || [], base);
    if (node.name === "a") {
      const href = link(node.attribs.href, base);
      return href ? [{ type: "link", href, children }] : children;
    }
    if (["strong", "b", "em", "i"].includes(node.name)) return [{ type: ["strong", "b"].includes(node.name) ? "strong" : "em", children }];
    return children;
  });
}

for (const [route, entries] of candidates) {
  entries.sort((a, b) => b.meta.at.localeCompare(a.meta.at));
  for (const { meta, file } of entries) {
    const html = fs.readFileSync(file, "utf8");
    if (!html.includes('class="page-header"') || !html.includes('class="navbar-brand"') || /<title>(?:年齢確認|Just a moment|エラー)/i.test(html)) continue;
    const $ = load(html);
    const slug = route.split("/")[1];
    if (route.includes("/download/")) {
      const fields = {};
      $("table tr").each((_, row) => { fields[$(row).children("th").text().trim()] = $(row).children("td").text().trim(); });
      if (!fields["ファイル"]) continue;
      archive.files[`${slug}/${route.split("/")[3]}`] = {
        displayName: fields["ファイル"], comment: fields["コメント"] || "",
        original: fields["オリジナル"] || fields["ファイル"], listedSize: fields["容量"] || null,
        fullDate: fields["日時"] || null, counter: fields["ダウンロード"] || null,
        md5: $("input[value]").toArray().map(input => $(input).attr("value")).find(value => /^[0-9a-f]{32}$/.test(value)) || null,
      };
    } else {
      const rows = [];
      $("table tbody tr").each((_, row) => {
        const cells = $(row).children("td");
        const id = cells.eq(0).find("a").attr("href")?.match(/\/download\/(\d+)/)?.[1];
        if (!id) return;
        assert.ok(knownFiles.has(`${slug}/${id}`), `Missing catalog file: ${slug}/${id}`);
        rows.push(id);
        listFields[`${slug}/${id}`] = { displayName: cells.eq(0).text().trim(), listComment: cells.eq(1).text().trim(), original: cells.eq(2).text().trim(), counter: cells.eq(5).text().trim() };
      });
      const pagination = $(".pagination").first().children("li").toArray().flatMap(item => {
        const href = $(item).find("a").attr("href");
        if (!href) return [];
        const page = Number(new URL(href, meta.requested_url).pathname.match(/\/index\/date\/desc\/(\d+)/)?.[1] || 1);
        return [{ page, kind: $(item).hasClass("previous") ? "previous" : $(item).hasClass("next") ? "next" : "page", active: $(item).hasClass("active") }];
      });
      archive.listings[route] = { uploader: slug, page: route.includes("/index/") ? Number(route.split("/").at(-1)) : 1, ids: rows, pagination };
      if (route === `/${slug}` || !archive.uploaders[slug]) {
        const information = [];
        $("table tr").each((_, row) => {
          const label = $(row).children("th").text().trim();
          const value = $(row).children("td").text().trim().replace(/\s*\[誤りを報告\]/g, "");
          if (label && value && label !== "ディスク" && !(label === "容量" && value.includes(" / "))) information.push({ label, value });
        });
        const homepage = $("a[href]").filter((_, anchor) => $(anchor).text().trim() === "ホームページへ戻る").first();
        archive.uploaders[slug] = {
          title: $(".navbar-brand").first().text().trim(),
          description: rich($(".page-header").parent().find(".lead").first().contents().toArray(), meta.requested_url),
          information, homepage: link(homepage.attr("href"), meta.requested_url),
        };
      }
    }
    break;
  }
}
for (const [key, fields] of Object.entries(listFields)) {
  const detail = archive.files[key];
  archive.files[key] = { ...fields, ...detail, counter: detail?.counter ?? fields.counter, listComment: fields.listComment };
  if (!detail) archive.files[key].hasDetail = false;
}
for (const fields of Object.values(archive.files)) fields.hasDetail ??= true;
assert.equal(Object.keys(archive.uploaders).length, catalog.groups.length);
for (const group of catalog.groups) assert.ok(archive.listings[`/${group.slug}`], `Missing uploader entry: ${group.slug}`);
const missing = catalog.files.filter(file => !archive.files[`${file.uploader}/${file.id}`]?.hasDetail).map(file => `${file.uploader}/${file.id}`);
compactArchive(archive, catalog);
fs.writeFileSync("src/data/archive.json", JSON.stringify(archive) + "\n");
fs.mkdirSync("local/reports", { recursive: true });
fs.writeFileSync("local/reports/archive-import.json", JSON.stringify({ unreadable, missing }, null, 2));
console.log(JSON.stringify({ uploaders: Object.keys(archive.uploaders).length, details: Object.values(archive.files).filter(file => file.hasDetail).length, listings: Object.keys(archive.listings).length, missing: missing.length }));
