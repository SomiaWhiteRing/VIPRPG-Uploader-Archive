import "./globals.css";
import { LanguageProvider } from "@/components/language-context";


export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="zh-CN" data-language-pending=""><head>
    <link rel="icon" href="/vendor/uploader/favicon.ico" type="image/x-icon" />
    {/* eslint-disable @next/next/no-css-tags -- Preserve the source CSS and its browser parsing behavior. */}
    <link rel="stylesheet" href="/vendor/uploader/bootstrap.min.css" precedence="uploader" />
    <link rel="stylesheet" href="/vendor/uploader/uploader.css" precedence="uploader" />
    <link rel="stylesheet" href="/vendor/uploader/rwd-table.min.css" precedence="uploader" />
  </head><body><noscript><style>{"html[data-language-pending] body { opacity: 1; pointer-events: auto; }"}</style></noscript><LanguageProvider>{children}</LanguageProvider></body></html>;
}
