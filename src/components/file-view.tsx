"use client";

import Link from "next/link";
import ArchiveChrome from "@/components/archive-chrome";
import { useLanguage } from "@/components/language-context";
import { canDownload, downloadUrl, fileStatus, type ArchiveFile } from "@/lib/files";
import type { FileDetails } from "@/lib/archive-types";

export default function FileView({ file, details, uploaderTitle, uploaderAvailable }: {
  file: ArchiveFile; details?: FileDetails; uploaderTitle: string; uploaderAvailable: boolean;
}) {
  const { t, language } = useLanguage();
  const name = details?.displayName || file.name || `${t("文件", "ファイル")} #${file.id}`;
  const md5 = file.supplement?.md5 || details?.md5;
  return <ArchiveChrome title={uploaderTitle} slug={uploaderAvailable ? file.uploader : undefined}>
    <div className="container"><div className="page-header"><h2 className="h1">{uploaderTitle} <small>uploader.jp</small></h2></div>
      <h1 className="lead">{uploaderAvailable ? <Link prefetch={false} href={`/${file.uploader}`}>{uploaderTitle}</Link> : uploaderTitle}{t(" 中的文件：", " より、")}<strong>{name}</strong>{t("", " をダウンロードします。")}</h1>
    </div>
    <div className="container"><div className="row"><div className="col-sm-8 col-sm-offset-2">
      {!details?.hasDetail && <p className="text-muted">{t("尚无可还原的原文件页面，以下仅显示已保存的索引。", "元のファイルページを復元できないため、保存済みのファイル情報のみを表示しています。")}</p>}
      <table className="table space"><caption><span className="glyphicon glyphicon-file" aria-hidden="true" /> <em>{t("下载详情：", "ダウンロード情報：")}</em></caption><tbody>
        <tr><th style={{ width: 100 }}>{t("文件", "ファイル")}</th><td>{name}</td></tr>
        <tr><th>{t("评论", "コメント")}</th><td><strong style={{ whiteSpace: "pre-wrap" }}>{details?.comment || details?.listComment || ""}</strong></td></tr>
        <tr><th>{t("原文件名", "オリジナル")}</th><td>{details?.original || file.name || "—"}</td></tr>
        <tr><th>{t("容量", "容量")}</th><td>{details?.listedSize || file.listedSize || (file.size == null ? "—" : `${file.size.toLocaleString("en-US")} ${t("字节", "バイト")}`)}</td></tr>
        <tr><th>{t("时间", "日時")}</th><td>{details?.fullDate || file.date || "—"}</td></tr>
        {details?.counter && <tr><th>{t("下载次数", "ダウンロード")}</th><td>{details.counter}</td></tr>}
        <tr><th>{t("归档状态", "保存状況")}</th><td>{fileStatus(file, language)}</td></tr>
      </tbody></table>
      <div className="text-center space">{canDownload(file)
        ? <a className="btn btn-default btn-xs" href={downloadUrl(file)}>{file.requiresUnwrap && !file.supplement ? t("下载分卷容器 ZIP", "分割ファイルを収めた ZIP をダウンロード") : t("下载", "ダウンロード")}</a>
        : <><button className="btn btn-default btn-xs" type="button" disabled>{t("下载", "ダウンロード")}</button><p className="text-muted">{fileStatus(file, language)}</p></>}
      </div>
      {file.requiresUnwrap && !file.supplement && <p className="text-warning">{t("下载后先解包，取出原分卷：", "ダウンロード後に ZIP を展開し、元の分割ファイルを取り出してください：")}{file.archiveMember}</p>}
      <div className="form-group"><label htmlFor="original-url"><span className="glyphicon glyphicon-link" aria-hidden="true" /> {t("原页面链接", "元のページの URL")}</label><input id="original-url" className="form-control" value={file.sourceUrl} readOnly /></div>
      {md5 && <div className="form-group"><label htmlFor="original-md5"><span className="glyphicon glyphicon-save-file" aria-hidden="true" /> {t("MD5 校验值", "MD5 チェックサム")}</label><input id="original-md5" className="form-control" value={md5} readOnly /></div>}
      <p className="space"><Link className="btn btn-default" prefetch={false} href={uploaderAvailable ? `/${file.uploader}` : "/"}><span className="glyphicon glyphicon-chevron-left" aria-hidden="true" /> {t("返回目录", "一覧に戻る")}</Link></p>
    </div></div></div>
  </ArchiveChrome>;
}
