"use client";

import Link from "next/link";
import { useState } from "react";
import { useLanguage } from "@/components/language-context";
import ArchiveNotice from "@/components/archive-notice";
import directorySource from "@/data/directory-source.json";

export default function ArchiveChrome({ title, slug, children }: { title?: string; slug?: string; children: React.ReactNode }) {
  const { t } = useLanguage();
  const [menuOpen, setMenuOpen] = useState(false);
  return <>
    <nav className="navbar navbar-default navbar-fixed-top"><div className="container">
      <div className="navbar-header"><button type="button" className="navbar-toggle collapsed" aria-label={t("展开导航", "メニューを開く")} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}><span className="icon-bar" /><span className="icon-bar" /><span className="icon-bar" /></button><Link className="navbar-brand" href={slug ? `/${slug}` : "/"}>{title || t("VIPRPG 上传区保存库", "VIPRPG アップローダー保存庫")}</Link></div>
      <div id="navbar" className={`navbar-collapse collapse${menuOpen ? " in" : ""}`}><ul className="nav navbar-nav">{slug && <li><Link href={`/${slug}`}>{t("文件列表", "一覧")}</Link></li>}<li><Link href="/">{t("上传区目录", "アップローダー一覧")}</Link></li><li><a href="https://archive.org/details/viprpg-uploader-archive">Internet Archive</a></li></ul></div>
    </div></nav>
    {(title || slug) && <ArchiveNotice />}
    {children}
    <div className="container"><footer className="footer space pull-right"><p className="text-muted">{t("VIPRPG 上传区保存库 · 文件由 Internet Archive 提供。", "VIPRPG アップローダー保存庫 · ファイル提供：Internet Archive")}<br />{t("情报来源：", "情報源：")}<a href={directorySource.url}>Neocities</a> · {t("原上传区页面", "各アップローダーの元ページ")}</p></footer></div>
  </>;
}
