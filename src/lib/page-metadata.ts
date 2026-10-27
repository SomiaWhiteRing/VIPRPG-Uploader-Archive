export type PageInfo = { initialTitle: string; title: { zh: string; ja: string }; description: { zh: string; ja: string } };
export const siteName = { zh: "VIPRPG 上传区保存库", ja: "VIPRPG アップローダー保存庫" };

export const homeInfo: PageInfo = {
  initialTitle: "VIPRPG",
  title: siteName,
  description: {
    zh: "按原上传区与文件编号检索 uploader.jp 的 VIPRPG 文件存档。",
    ja: "uploader.jp から保存した VIPRPG 関連ファイルを、元のアップローダー名やファイル番号で探せます。",
  },
};
export const notFoundInfo: PageInfo = {
  initialTitle: "VIPRPG",
  title: { zh: `未收录此上传区或文件 | ${siteName.zh}`, ja: `ページが見つかりません | ${siteName.ja}` },
  description: { zh: "请核对上传区名称和文件编号，或返回目录通过原链接查找。", ja: "アップローダー名とファイル番号をご確認ください。アップローダー一覧では、元の URL からも検索できます。" },
};

export function uploaderInfo(name: string, page?: string): PageInfo {
  return {
    initialTitle: `${name}${page ? ` · ${page}` : ""} | VIPRPG`,
    title: { zh: `${name}${page ? ` - 第 ${page} 页` : ""} | ${siteName.zh}`, ja: `${name}${page ? ` - ${page}ページ` : ""} | ${siteName.ja}` },
    description: { zh: `浏览 ${name} 的归档文件列表${page ? `，第 ${page} 页` : ""}，查看原文件信息与下载状态。`, ja: `${name} から保存したファイルの一覧${page ? `（${page}ページ）` : ""}。元のファイル情報とダウンロードの可否を確認できます。` },
  };
}

export function searchInfo(name: string): PageInfo {
  return {
    initialTitle: `${name} | VIPRPG`,
    title: { zh: `搜索 - ${name} | ${siteName.zh}`, ja: `検索 - ${name} | ${siteName.ja}` },
    description: { zh: `在 ${name} 中搜索归档文件名、编号和评论。`, ja: `${name} から保存したファイルを、ファイル名・番号・コメントで検索できます。` },
  };
}

export function fileInfo(name: string | null | undefined, id: string, uploader: string): PageInfo {
  return {
    initialTitle: `${name || `#${id}`} | VIPRPG`,
    title: { zh: `${name || `文件 #${id}`} | ${siteName.zh}`, ja: `${name || `ファイル #${id}`} | ${siteName.ja}` },
    description: { zh: `查看 ${uploader} 中 ${name || `文件 #${id}`} 的原始信息、归档状态与下载入口。`, ja: `${uploader} に投稿された ${name || `ファイル #${id}`} の詳細情報、保存状況、ダウンロード先を確認できます。` },
  };
}

export function staticMetadata(info: PageInfo) {
  return {
    title: { absolute: info.initialTitle }, description: info.description.zh,
    openGraph: { title: info.title.zh, description: info.description.zh, siteName: siteName.zh, locale: "zh_CN" },
    twitter: { card: "summary" as const, title: info.title.zh, description: info.description.zh },
  };
}
