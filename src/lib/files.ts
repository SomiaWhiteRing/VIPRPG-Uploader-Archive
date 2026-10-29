import type { FileDetails } from "@/lib/archive-types";

export interface Uploader {
  slug: string;
  sourceUrl: string;
  total: number;
  counts: Partial<Record<string, number>>;
}

export interface ArchiveFile {
  uploader: string;
  id: string;
  name: string | null;
  sourceUrl: string;
  listedSize: string | null;
  date: string | null;
  size: number | null;
  localState: string;
  state: string;
  remotePath: string | null;
  requiresUnwrap: boolean;
  archiveMember: string | null;
  supplement?: {
    url: string;
    md5: string;
    size: number;
    modified: boolean;
    releaseUrl: string;
  };
}

export type ListedFile = Pick<ArchiveFile, "uploader" | "id" | "name" | "listedSize" | "date" | "size" | "localState">
  & Partial<Pick<FileDetails, "displayName" | "comment" | "listComment" | "original" | "counter">>;

export function filePath(file: Pick<ArchiveFile, "uploader" | "id">) {
  return `/${file.uploader}/download/${file.id}`;
}

export function downloadUrl(file: ArchiveFile) {
  if (file.supplement) return file.supplement.url;
  return `https://archive.org/download/VIPRPG-uploaderjp-Archive/${file.remotePath?.split("/").map(encodeURIComponent).join("/")}`;
}

export function fileStatus(file: ArchiveFile, language: "zh" | "ja" = "zh") {
  if (file.supplement || file.state === "indexed") return language === "ja" ? "ダウンロード可能" : "可下载";
  if (file.state === "accepted") return language === "ja" ? "公開インデックスへの反映待ち" : "等待公开索引";
  if (file.state === "failed") return language === "ja" ? "アップロードに失敗" : "上传失败";
  if (file.localState === "skipped_password") return language === "ja" ? "パスワード付き・未保存" : "密码文件未保存";
  if (file.localState === "skipped_source_missing") return language === "ja" ? "元ファイルなし" : "源文件已失效";
  if (file.localState === "done") return language === "ja" ? "アップロード待ち" : "等待上传";
  return language === "ja" ? "未保存" : "尚未保存";
}

