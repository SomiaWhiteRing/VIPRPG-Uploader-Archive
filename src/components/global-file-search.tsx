"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useLanguage } from "@/components/language-context";
import { filePath, type ListedFile } from "@/lib/files";

type SearchFile = ListedFile & { uploaderTitle: string };
type Field = "all" | "filename" | "original" | "comment" | "uploader" | "id";
type Sort = "date" | "counter" | "filename" | "size" | "uploader";
const PAGE_SIZE = 20;

export default function GlobalFileSearch() {
  const { t } = useLanguage();
  const [files, setFiles] = useState<SearchFile[] | null>(null);
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [field, setField] = useState<Field>("all");
  const [sort, setSort] = useState<Sort>("date");
  const [ascending, setAscending] = useState(false);
  const [page, setPage] = useState(1);
  const [searched, setSearched] = useState(false);
  const [searching, setSearching] = useState(false);

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (files || []).filter(file => {
      const fields = {
        filename: [file.displayName, file.name], original: [file.original, file.name],
        comment: [file.comment, file.listComment], uploader: [file.uploader, file.uploaderTitle], id: [file.id],
      };
      return (field === "all" ? Object.values(fields).flat() : fields[field]).some(value => value?.toLowerCase().includes(needle));
    }).sort((a, b) => {
      const value = (file: SearchFile) => sort === "counter" ? (file.counter ? Number(file.counter.replaceAll(",", "")) : null)
        : sort === "size" ? file.size : sort === "filename" ? file.displayName || file.name : sort === "uploader" ? file.uploaderTitle : file.date?.replace(/^(\d{2})\//, "20$1/");
      const left = value(a), right = value(b);
      if (left == null || left === "") return right == null || right === "" ? 0 : 1;
      if (right == null || right === "") return -1;
      const comparison = typeof left === "number" && typeof right === "number" ? left - right : String(left).localeCompare(String(right), "ja");
      return ascending ? comparison : -comparison;
    });
  }, [files, query, field, sort, ascending]);
  const pages = Math.max(1, Math.ceil(results.length / PAGE_SIZE));
  const sortButtons = (next: Sort, zh: string, ja: string) => <span className="global-sort-buttons">
    <button type="button" aria-label={t(`${zh}升序`, `${ja}で昇順に並べ替え`)} aria-pressed={sort === next && ascending} onClick={() => { setSort(next); setAscending(true); setPage(1); }}>▴</button>
    <button type="button" aria-label={t(`${zh}降序`, `${ja}で降順に並べ替え`)} aria-pressed={sort === next && !ascending} onClick={() => { setSort(next); setAscending(false); setPage(1); }}>▾</button>
  </span>;

  return <div className="container global-search">
    <div className="page-header"><h1>{t("文件搜索", "ファイル検索")}</h1></div>
    <form className="form-inline space" onSubmit={event => {
      event.preventDefault();
      setQuery(input);
      setPage(1);
      setSearched(true);
      if (!files) {
        setSearching(true);
        fetch("/search-data.json").then(response => {
          if (!response.ok) throw new Error("Search data request failed");
          return response.json();
        }).then(setFiles).catch(() => setSearched(false)).finally(() => setSearching(false));
      }
    }}>
      <div className="form-group"><label className="sr-only" htmlFor="global-query">{t("关键词", "キーワード")}</label>
      <input className="form-control" id="global-query" type="search" value={input} onChange={event => setInput(event.target.value)} placeholder={t("查找文件…", "ファイルを検索…")} /></div>{" "}
      <button className="btn btn-default" type="submit" disabled={searching}>{searching ? t("搜索中…", "検索中…") : t("搜索", "検索")}</button>
    </form>
    <div className="global-search-options form-inline space">
      <label htmlFor="global-field">{t("搜索字段", "検索対象")}</label>{" "}<select className="form-control" id="global-field" value={field} onChange={event => { setField(event.target.value as Field); setPage(1); }}>
        <option value="all">{t("全部字段", "すべての項目")}</option><option value="filename">{t("文件名", "ファイル名")}</option><option value="original">{t("原文件名", "元のファイル名")}</option><option value="comment">{t("评论", "コメント")}</option><option value="uploader">{t("上传区", "アップローダー")}</option><option value="id">{t("文件编号", "ファイル番号")}</option>
      </select>{" "}
    </div>
    <div aria-live="polite" aria-busy={searching}>
    {searched && files && !searching && <p className="text-muted">{t(`搜索结果 ${results.length.toLocaleString("en-US")} 件`, `検索結果：${results.length.toLocaleString("en-US")}件`)}</p>}
    <div className="table-responsive" data-pattern="priority-columns"><table className="table table-small-font table-hover"><thead><tr>
      <th>{t("文件", "ファイル")} {sortButtons("filename", "文件名", "ファイル名")}</th><th>{t("评论", "コメント")}</th><th>{t("上传区", "アップローダー")} {sortButtons("uploader", "上传区", "アップローダー")}</th><th>{t("容量", "容量")} {sortButtons("size", "容量", "容量")}</th><th>{t("时间", "日時")} {sortButtons("date", "时间", "日時")}</th><th>{t("下载次数", "ダウンロード数")} {sortButtons("counter", "下载次数", "ダウンロード数")}</th>
    </tr></thead><tbody>{searched && files && !searching && results.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map((file, index) => <tr key={`${file.uploader}/${file.id}`} className={index % 2 ? "alt" : undefined}>
      <td className="global-search-filename"><Link prefetch={false} href={filePath(file)}>{file.displayName || file.name || `${t("文件", "ファイル")} #${file.id}`}</Link></td><td className="global-search-comment">{file.comment || file.listComment || ""}</td><td className="global-search-uploader"><Link prefetch={false} href={`/${file.uploader}`}>{file.uploaderTitle}</Link></td><td>{file.listedSize || "—"}</td><td>{file.date || "—"}</td><td>{file.counter || "—"}</td>
    </tr>)}{(!searched || searching || (files && !results.length)) && <tr><td colSpan={6} className="text-center text-muted global-search-empty">{searching ? t("正在搜索…", "検索しています…") : !searched ? t("输入关键词并搜索。", "キーワードを入力して検索してください。") : t("没有匹配的文件，请尝试其他关键词或搜索字段。", "条件に一致するファイルが見つかりませんでした。キーワードや検索対象を変えて、もう一度検索してください。")}</td></tr>}</tbody></table></div>
    {searched && files && !searching && pages > 1 && <nav className="text-center" aria-label={t("文件分页", "ページ切り替え")}><ul className="pagination pagination-sm"><li className={page === 1 ? "disabled" : "previous"}><a href="#" onClick={event => { event.preventDefault(); if (page > 1) setPage(page - 1); }}>{t("上一页", "前へ")}</a></li>{Array.from({ length: pages }, (_, index) => index + 1).filter(number => Math.abs(number - page) <= 2 || number === 1 || number === pages).map(number => <li key={number} className={number === page ? "active" : "page"}><a href="#" onClick={event => { event.preventDefault(); setPage(number); }}>{number}</a></li>)}<li className={page === pages ? "disabled" : "next"}><a href="#" onClick={event => { event.preventDefault(); if (page < pages) setPage(page + 1); }}>{t("下一页", "次へ")}</a></li></ul></nav>}
    </div>
  </div>;
}
