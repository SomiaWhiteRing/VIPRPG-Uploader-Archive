import "./globals.css";
import { LanguageProvider } from "@/components/language-context";


export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="zh-CN" data-language-pending=""><head>
    <link rel="icon" href={`${process.env.NEXT_PUBLIC_BASE_PATH || ""}/vendor/uploader/favicon.ico`} type="image/x-icon" />
    {/* eslint-disable @next/next/no-css-tags -- Preserve the source CSS and its browser parsing behavior. */}
    <link rel="stylesheet" href={`${process.env.NEXT_PUBLIC_BASE_PATH || ""}/vendor/uploader/bootstrap.min.css`} precedence="uploader" />
    <link rel="stylesheet" href={`${process.env.NEXT_PUBLIC_BASE_PATH || ""}/vendor/uploader/uploader.css`} precedence="uploader" />
    <link rel="stylesheet" href={`${process.env.NEXT_PUBLIC_BASE_PATH || ""}/vendor/uploader/rwd-table.min.css`} precedence="uploader" />
  </head><body><noscript><style>{"html[data-language-pending] body { opacity: 1; pointer-events: auto; }"}</style></noscript><LanguageProvider>{children}</LanguageProvider></body></html>;
}
