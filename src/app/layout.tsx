import type { Metadata } from "next";
import "./globals.css";
import { LanguageProvider } from "@/components/language-context";
import { homeInfo, staticMetadata } from "@/lib/page-metadata";

export const metadata: Metadata = staticMetadata(homeInfo);

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="zh-CN" data-language-pending=""><head>
    <link rel="icon" href="/vendor/uploader/favicon.ico" type="image/x-icon" />
    <noscript><style>{"html[data-language-pending] body { opacity: 1; pointer-events: auto; }"}</style></noscript>
    {/* eslint-disable @next/next/no-css-tags -- Preserve the source CSS and its browser parsing behavior. */}
    <link rel="stylesheet" href="/vendor/uploader/bootstrap.min.css" />
    <link rel="stylesheet" href="/vendor/uploader/uploader.css" />
    <link rel="stylesheet" href="/vendor/uploader/rwd-table.min.css" />
  </head><body><LanguageProvider>{children}</LanguageProvider></body></html>;
}
