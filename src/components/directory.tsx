"use client";

import Link from "next/link";
import { useState } from "react";
import type { Uploader } from "@/lib/files";
import foldersJson from "@/data/directory.json";
import { useLanguage } from "@/components/language-context";

type Folder = { zh: string; ja: string; slugs: string[]; children?: Folder[] };

export default function Directory({ groups }: { groups: (Uploader & { title: string })[] }) {
  const [query, setQuery] = useState("");
  const { t } = useLanguage();
  const matching = groups.filter(group => `${group.slug} ${group.title}`.toLowerCase().includes(query.trim().toLowerCase()));
  const bySlug = new Map(matching.map(group => [group.slug, group]));
  function renderFolder(folder: Folder, level = 0): React.ReactNode {
    const children = folder.children || [];
    const slugs = [...folder.slugs, ...children.flatMap(child => child.slugs)];
    const count = slugs.filter(slug => bySlug.has(slug)).length;
    if (!count) return null;
    return <details key={folder.zh} className={level === 0 ? "directory-category panel panel-default" : "directory-festival"} open={query.trim() ? true : undefined}>
      <summary><span className="glyphicon glyphicon-folder-open" aria-hidden="true" /><span className="directory-name">{t(folder.zh, folder.ja)}</span><span className="badge" title={t(`${count} 个上传区`, `アップローダー ${count} 件`)}>{count}</span></summary>
      <div className={`directory-children${children.length ? " directory-festivals" : ""}`}>
        {children.map(child => renderFolder(child, level + 1))}
        {folder.slugs.some(slug => bySlug.has(slug)) && <div className="table-responsive"><table className="table table-small-font table-hover"><colgroup><col /><col className="directory-count" /><col className="directory-count" /><col className="directory-source" /></colgroup><thead><tr><th>{t("上传区", "アップローダー")}</th><th className="text-right">{t("文件记录", "ファイル")}</th><th className="text-right">{t("可下载", "ダウンロード可能")}</th><th className="text-right">{t("原站", "元サイト")}</th></tr></thead><tbody>
          {folder.slugs.map(slug => { const group = bySlug.get(slug); return group && <tr key={slug}><td><Link href={`/${slug}`} title={slug}>{group.title}</Link></td><td className="text-right">{group.total.toLocaleString("en-US")}</td><td className="text-right">{(group.counts.indexed ?? 0).toLocaleString("en-US")}</td><td className="text-right"><a href={group.sourceUrl}>{t("原上传区", "元のページ")}</a></td></tr>; })}
        </tbody></table></div>}
      </div>
    </details>;
  }
  return <section className="directory">
    <div className="directory-toolbar"><label className="sr-only" htmlFor="group-search">{t("筛选上传区", "アップローダーを検索")}</label><input className="form-control" id="group-search" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder={t("查找上传区…", "アップローダーを検索…")} />{query.trim() && <span className="text-muted">{t(`${matching.length} 个结果`, `${matching.length} 件`)}</span>}</div>
    {(foldersJson as Folder[]).map(folder => renderFolder(folder))}
    {!matching.length && <p className="text-muted">{t("没有匹配的上传区。", "一致するアップローダーはありません。")}</p>}
  </section>;
}
