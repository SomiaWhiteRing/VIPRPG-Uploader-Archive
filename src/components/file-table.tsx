"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { filePath, type ListedFile } from "@/lib/files";
import type { Listing } from "@/lib/archive-types";
import { useLanguage } from "@/components/language-context";

const PAGE_SIZE = 20;

export default function FileTable({ files, listing }: { files: ListedFile[]; listing?: Listing }) {
  const { t } = useLanguage();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("date");
  const [ascending, setAscending] = useState(false);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setQuery(params.get("q") || "");
    const field = params.get("sort");
    if (field && ["date", "filename", "original", "filesize", "counter"].includes(field)) setSort(field);
    setAscending(params.get("order") === "asc");
  }, []);
  const visible = listing ? files : files.filter(file => `${file.id} ${file.name || ""} ${file.displayName || ""} ${file.comment || ""} ${file.listComment || ""}`.toLowerCase().includes(query.trim().toLowerCase()));
  if (!listing) visible.sort((a, b) => {
    let result: number;
    if (sort === "filesize") result = (a.size || 0) - (b.size || 0);
    else if (sort === "counter") result = Number(a.counter || 0) - Number(b.counter || 0);
    else if (sort === "filename") result = (a.displayName || a.name || "").localeCompare(b.displayName || b.name || "", "ja");
    else if (sort === "original") result = (a.original || a.name || "").localeCompare(b.original || b.name || "", "ja");
    else result = (a.date || "").localeCompare(b.date || "") || Number(a.id) - Number(b.id);
    return ascending ? result : -result;
  });
  const pages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  return <>
    <form className="form-inline space" action={listing ? `/${listing.uploader}/search` : undefined} method="GET" onSubmit={event => { if (!listing) { event.preventDefault(); setPage(1); } }}><div className="form-group"><label className="sr-only" htmlFor="file-search">{t("关键词", "キーワード")}</label><input className="form-control" id="file-search" name="q" type="search" placeholder={t("查找文件…", "ファイルを検索…")} value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} /></div>{" "}<button className="btn btn-default" type="submit">{t("搜索", "検索")}</button></form>
    <div className="space"><span className="btn btn-default btn-xs active"><span className="glyphicon glyphicon-list" aria-hidden="true" /> {t("文件列表", "一覧")}</span></div>
    <div className="table-responsive" data-pattern="priority-columns"><table cellSpacing="0" className="table table-small-font table-hover"><thead><tr>
      {[['filename','文件','ファイル'],['comment','评论','コメント'],['original','原文件名','オリジナル'],['filesize','容量','容量'],['date','时间','日時'],['counter','下载次数','ダウンロード数']].map(([field,zh,ja]) => <th key={field}>{field === 'comment' ? t(zh,ja) : <a href={listing ? `/${listing.uploader}/search?sort=${field}&order=asc` : "#"} onClick={listing ? undefined : event => { event.preventDefault(); setAscending(sort === field ? !ascending : true); setSort(field); setPage(1); }}>{t(zh,ja)}</a>}</th>)}
    </tr></thead><tbody>
      {(listing ? visible : visible.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)).map((file, index) => <tr key={file.id} className={index % 2 ? "alt" : undefined}><td><Link prefetch={false} href={filePath(file)} title={file.displayName || file.name || undefined}>{file.displayName || file.name || `${t("文件", "ファイル")} #${file.id}`}</Link></td><td>{file.localState === "skipped_password" && <><span className="glyphicon glyphicon-lock" aria-hidden="true" />{" "}</>}{listing ? file.listComment ?? file.comment ?? "" : file.comment || file.listComment || ""}</td><td>{file.original || file.name || ""}</td><td>{file.listedSize || "—"}</td><td>{file.date || "—"}</td><td>{file.counter || "—"}</td></tr>)}
    </tbody></table></div>
    {!visible.length && <p className="text-muted">{t("没有匹配的文件。", "一致するファイルはありません。")}</p>}
    {listing && !!listing.pagination.length && <nav className="text-center" aria-label={t("文件分页", "ページ切り替え")}><ul className="pagination pagination-sm">{listing.pagination.map((link, index) => <li key={index} className={link.active ? "active" : link.kind}><Link prefetch={false} href={`/${listing.uploader}/index/date/desc/${link.page}`}>{link.kind === "previous" ? t("上一页", "前へ") : link.kind === "next" ? t("下一页", "次へ") : link.page}</Link></li>)}</ul></nav>}
    {!listing && pages > 1 && <nav className="text-center" aria-label={t("文件分页", "ページ切り替え")}><ul className="pagination pagination-sm"><li className={page === 1 ? "disabled" : "previous"}><a href="#" onClick={event => { event.preventDefault(); if(page > 1) setPage(page - 1); }}>{t("上一页", "前へ")}</a></li>{Array.from({ length: pages }, (_, index) => index + 1).filter(number => Math.abs(number-page) <= 2 || number === 1 || number === pages).map(number => <li key={number} className={number === page ? "active" : "page"}><a href="#" onClick={event => { event.preventDefault(); setPage(number); }}>{number}</a></li>)}<li className={page === pages ? "disabled" : "next"}><a href="#" onClick={event => { event.preventDefault(); if(page < pages) setPage(page + 1); }}>{t("下一页", "次へ")}</a></li></ul></nav>}
  </>;
}
