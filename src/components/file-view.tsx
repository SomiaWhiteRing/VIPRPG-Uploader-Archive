"use client";

import Link from "next/link";
import ArchiveChrome from "@/components/archive-chrome";
import ArchiveNotice from "@/components/archive-notice";
import { useLanguage } from "@/components/language-context";
import { canDownload, downloadUrl, fileStatus, type ArchiveFile } from "@/lib/files";
import type { FileDetails } from "@/lib/archive-types";

export default function FileView({ file, details, uploaderTitle, uploaderAvailable }: {
  file: ArchiveFile; details?: FileDetails; uploaderTitle: string; uploaderAvailable: boolean;
}) {
  const { t, language } = useLanguage();
  const name = details?.displayName || file.name || `${t("文件", "ファイル")} #${file.id}`;
  const md5 = file.supplement?.md5 || details?.md5;
  const supplementUrl = file.supplement && new URL(file.supplement.url);
  const githubFilename = supplementUrl?.hostname === "github.com" ? decodeURIComponent(supplementUrl.pathname.split("/").pop()!) : undefined;
  return <ArchiveChrome title={uploaderTitle} slug={uploaderAvailable ? file.uploader : undefined}>
    {githubFilename && <ArchiveNotice dismissible={false}>
      {t(`本文件托管于Github Releases。由于托管系统限制，下载的文件名（${githubFilename}）会与原本的名称有所不同。`, `このファイルは GitHub Releases で配布しています。配布システムの制約により、ダウンロード時のファイル名（${githubFilename}）は元のファイル名と異なります。`)}
    </ArchiveNotice>}
    <div className="container"><div className="page-header"><h2 className="h1">{uploaderTitle} <small>uploader.jp</small></h2></div>
      <h1 className="lead">{uploaderAvailable ? <Link prefetch={false} href={`/${file.uploader}`}>{uploaderTitle}</Link> : uploaderTitle}{t(" 中的文件：", " より、")}<strong>{name}</strong>{t("", " をダウンロードします。")}</h1>
    </div>
    <div className="container"><div className="row"><div className="col-sm-3 hidden-xs" style={{ maxWidth: 200 }} /><div className="col-sm-6">
      {!details?.hasDetail && <p className="text-muted">{t("未收录原下载详情页，以下信息来自已保存的目录索引。", "元のダウンロード詳細ページは未収録のため、以下は保存済みの一覧情報を表示しています。")}</p>}
      <table className="table space"><caption><span className="glyphicon glyphicon-file" aria-hidden="true" /> <em>{t("下载详情：", "Download Details:")}</em></caption><tbody>
        <tr><th style={{ width: 100 }}>{t("文件", "ファイル")}</th><td>{name}</td></tr>
        <tr><th>{t("评论", "コメント")}</th><td><strong style={{ whiteSpace: "pre-wrap" }}>{details?.comment || details?.listComment || ""}</strong></td></tr>
        <tr><th>{t("原文件名", "オリジナル")}</th><td>{details?.original || file.name || "—"}</td></tr>
        <tr><th>{t("容量", "容量")}</th><td>{details?.listedSize || file.listedSize || (file.size == null ? "—" : `${file.size.toLocaleString("en-US")} ${t("字节", "バイト")}`)}</td></tr>
        <tr><th>{t("时间", "日時")}</th><td>{details?.fullDate || file.date || "—"}</td></tr>
        {details?.counter && <tr><th>{t("下载次数", "ダウンロード")}</th><td>{details.counter}</td></tr>}
        <tr><th>{t("归档状态", "保存状況")}</th><td>{fileStatus(file, language)}</td></tr>
      </tbody></table>
      <div className="form-group"><label htmlFor="original-url"><span className="glyphicon glyphicon-link" aria-hidden="true" /> {t("原页面链接", "URL")}</label><input id="original-url" className="form-control" value={file.sourceUrl} readOnly /></div>
      {md5 && <div className="form-group"><label htmlFor="original-md5"><span className="glyphicon glyphicon-save-file" aria-hidden="true" /> {t("MD5 校验值", "MD5")}</label><input id="original-md5" className="form-control" value={md5} readOnly /></div>}
      {file.requiresUnwrap && !file.supplement && <p className="text-warning">{t("下载后先解包，取出原分卷：", "ダウンロード後に ZIP を展開し、元の分割ファイルを取り出してください：")}{file.archiveMember}</p>}
      <div className="text-center">{canDownload(file)
        ? <a className="btn btn-default btn-xs" href={downloadUrl(file)}>{file.requiresUnwrap && !file.supplement ? t("下载分卷容器 ZIP", "分割ファイルを収めた ZIP をダウンロード") : t("下载", "ダウンロード")}</a>
        : <><button className="btn btn-default btn-xs" type="button" disabled>{t("下载", "ダウンロード")}</button><p className="text-muted">{fileStatus(file, language)}</p></>}
      </div>
    </div></div></div>
    <div className="container"><Link className="btn btn-default space" prefetch={false} href={uploaderAvailable ? `/${file.uploader}` : "/"}><span className="glyphicon glyphicon-chevron-left" aria-hidden="true" /> {t("返回目录", uploaderAvailable ? `${uploaderTitle}へ戻る` : "一覧に戻る")}</Link></div>
  </ArchiveChrome>;
}
