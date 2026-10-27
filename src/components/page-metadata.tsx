"use client";

import { useLayoutEffect } from "react";
import { useLanguage } from "@/components/language-context";
import { siteName, type PageInfo } from "@/lib/page-metadata";

export default function PageMetadata({ info }: { info: PageInfo }) {
  const { language } = useLanguage();
  const title = info.title[language];
  const description = info.description[language];
  useLayoutEffect(() => {
    document.title = title;
    const tags = [
      ["name", "description", description],
      ["property", "og:title", title], ["property", "og:description", description],
      ["property", "og:site_name", siteName[language]], ["property", "og:locale", language === "ja" ? "ja_JP" : "zh_CN"],
      ["name", "twitter:title", title], ["name", "twitter:description", description],
    ];
    for (const [attribute, key, content] of tags) {
      let meta = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
      if (!meta) { meta = document.createElement("meta"); meta.setAttribute(attribute, key); document.head.appendChild(meta); }
      meta.content = content;
    }
  }, [title, description, language]);
  return null;
}
