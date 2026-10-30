"use client";

import { useLanguage } from "@/components/language-context";
import { siteName, type PageInfo } from "@/lib/page-metadata";

export default function PageMetadata({ info }: { info: PageInfo }) {
  const { language, ready } = useLanguage();
  const metadataLanguage = ready ? language : "ja";
  const title = info.title[metadataLanguage];
  const description = info.description[metadataLanguage];
  return <>
    <title>{title}</title>
    <meta name="description" content={description} />
    <meta property="og:title" content={title} />
    <meta property="og:description" content={description} />
    <meta property="og:site_name" content={siteName[metadataLanguage]} />
    <meta property="og:locale" content={metadataLanguage === "ja" ? "ja_JP" : "zh_CN"} />
    <meta name="twitter:card" content="summary" />
    <meta name="twitter:title" content={title} />
    <meta name="twitter:description" content={description} />
  </>;
}
