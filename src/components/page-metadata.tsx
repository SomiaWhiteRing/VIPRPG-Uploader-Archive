"use client";

import { useLanguage } from "@/components/language-context";
import { siteName, type PageInfo } from "@/lib/page-metadata";

export default function PageMetadata({ info }: { info: PageInfo }) {
  const { language, ready } = useLanguage();
  const title = ready ? info.title[language] : info.initialTitle;
  const description = info.description[language];
  return <>
    <title>{title}</title>
    <meta name="description" content={description} />
    <meta property="og:title" content={info.title[language]} />
    <meta property="og:description" content={description} />
    <meta property="og:site_name" content={siteName[language]} />
    <meta property="og:locale" content={language === "ja" ? "ja_JP" : "zh_CN"} />
    <meta name="twitter:card" content="summary" />
    <meta name="twitter:title" content={info.title[language]} />
    <meta name="twitter:description" content={description} />
  </>;
}
