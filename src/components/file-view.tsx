"use client";

import Link from "next/link";
import ArchiveChrome from "@/components/archive-chrome";
import { useLanguage } from "@/components/language-context";
import { downloadUrl, fileStatus, type ArchiveFile } from "@/lib/files";
import type { FileDetails } from "@/lib/archive-types";

export default function FileView({ file, details, uploaderTitle, uploaderAvailable }: {
  file: ArchiveFile; details?: FileDetails; uploaderTitle: string; uploaderAvailable: boolean;
}) {
  const { t, language } = useLanguage();
  const name = details?.displayName || file.name || `${t("文件", "ファイル")} #${file.id}`;
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
        {file.supplement && <tr><th>{t("补充文件", "補完ファイル")}</th><td>{file.supplement.size.toLocaleString("en-US")} {t("字节", "バイト")}</td></tr>}
      </tbody></table>
      <div className="text-center space">{file.supplement || (file.state === "indexed" && file.remotePath)
        ? <a className="btn btn-default btn-xs" href={downloadUrl(file)}>{file.supplement?.modified ? t("下载清理版", "変更済み保存版をダウンロード") : file.supplement ? t("下载补充存档", "補完アーカイブをダウンロード") : file.requiresUnwrap ? t("下载分卷容器 ZIP", "分割ファイルを収めた ZIP をダウンロード") : t("下载", "ダウンロード")}</a>
        : <><button className="btn btn-default btn-xs" type="button" disabled>{t("下载", "ダウンロード")}</button><p className="text-muted">{fileStatus(file, language)}</p></>}
      </div>
      {file.supplement && <p className="text-warning">{file.supplement.modified
        ? t("此清理版已移除可疑自解压 EXE，剩余 JPG 保持原样；文件与原包不同。", "この保存版は不審な自己解凍 EXE を除去し、残りの JPG をそのまま保持しています。元のアーカイブとは異なります。")
        : t("此补充存档由 GitHub Releases 提供。", "この補完アーカイブは GitHub Releases で提供しています。")}{" "}<a href={file.supplement.releaseUrl}>{t("查看来源与检查记录", "出典・確認記録を見る")}</a></p>}
      {file.requiresUnwrap && !file.supplement && <p className="text-warning">{t("下载后先解包，取出原分卷：", "ダウンロード後に ZIP を展開し、元の分割ファイルを取り出してください：")}{file.archiveMember}</p>}
      <div className="form-group"><label htmlFor="original-url"><span className="glyphicon glyphicon-link" aria-hidden="true" /> {t("原页面链接", "元のページの URL")}</label><input id="original-url" className="form-control" value={file.sourceUrl} readOnly /></div>
      {details?.md5 && <div className="form-group"><label htmlFor="original-md5"><span className="glyphicon glyphicon-save-file" aria-hidden="true" /> {file.supplement?.modified ? t("原包 MD5", "元のアーカイブの MD5") : t("MD5 校验值", "MD5 チェックサム")}</label><input id="original-md5" className="form-control" value={details.md5} readOnly /></div>}
      {file.supplement && <div className="form-group"><label htmlFor="supplement-md5">{t("补充下载文件 MD5", "補完ダウンロードファイルの MD5")}</label><input id="supplement-md5" className="form-control" value={file.supplement.md5} readOnly /></div>}
      <p className="space"><Link className="btn btn-default" prefetch={false} href={uploaderAvailable ? `/${file.uploader}` : "/"}><span className="glyphicon glyphicon-chevron-left" aria-hidden="true" /> {t("返回目录", "一覧に戻る")}</Link></p>
    </div></div></div>
  </ArchiveChrome>;
}
