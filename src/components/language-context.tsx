"use client";

import { createContext, useContext, useLayoutEffect, useState } from "react";
import { createPortal } from "react-dom";
import { usePathname } from "next/navigation";
import Image from "next/image";

type Language = "zh" | "ja";
const LanguageContext = createContext({ language: "zh" as Language, ready: false, t: (zh: string, ja: string) => zh || ja });

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState<Language>("zh");
  const [initialized, setInitialized] = useState(false);
  const [target, setTarget] = useState<HTMLElement | null>(null);
  const pathname = usePathname();
  useLayoutEffect(() => {
    const saved = localStorage.getItem("uploader-language");
    setLanguage(saved === "ja" || saved === "zh" ? saved : navigator.language.startsWith("ja") ? "ja" : "zh");
    setInitialized(true);
  }, []);
  useLayoutEffect(() => { setTarget(document.getElementById("navbar")); }, [pathname]);
  useLayoutEffect(() => {
    if (!initialized) return;
    document.documentElement.lang = language === "ja" ? "ja" : "zh-CN";
    document.documentElement.removeAttribute("data-language-pending");
  }, [language, initialized, pathname]);
  return <LanguageContext.Provider value={{ language, ready: initialized, t: (zh, ja) => language === "ja" ? ja : zh }}>
    {children}
    {target && createPortal(<ul className="nav navbar-nav navbar-right"><li><a href="#" lang={language === "ja" ? "ja" : "zh-CN"} aria-label={language === "ja" ? "現在の言語：日本語。中国語に切り替え" : "当前语言：中文。切换到日语"} title={language === "ja" ? "中国語に切り替え" : "切换到日语"} onClick={event => {
      event.preventDefault();
      const next = language === "ja" ? "zh" : "ja";
      setLanguage(next);
      localStorage.setItem("uploader-language", next);
    }}><Image src={`/icon/language-${language}.svg`} alt={language === "ja" ? "日本語" : "中文"} width={24} height={16} unoptimized /></a></li></ul>, target)}
  </LanguageContext.Provider>;
}

export function useLanguage() { return useContext(LanguageContext); }
export function Text({ zh, ja }: { zh: string; ja: string }) { return useLanguage().t(zh, ja); }
