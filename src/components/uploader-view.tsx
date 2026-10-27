"use client";

import ArchiveChrome from "@/components/archive-chrome";
import FileTable from "@/components/file-table";
import RichText from "@/components/rich-text";
import { useLanguage } from "@/components/language-context";
import type { Listing, UploaderDetails } from "@/lib/archive-types";
import type { ListedFile } from "@/lib/files";

export default function UploaderView({ slug, details, listing, files }: {
  slug: string; details: UploaderDetails; listing: Listing; files: ListedFile[];
}) {
  const { t } = useLanguage();
  const labels: Record<string, string> = { "ファイル": "文件", "ダウンロード": "下载", "レーティング": "分级" };
  return <ArchiveChrome title={details.title} slug={slug}>
    <div className="container"><div className="page-header"><h1>{details.title} <small>uploader.jp</small></h1></div>
      {!!details.description.length && <h2 className="lead"><RichText nodes={details.description} /></h2>}
    </div>
    <div className="container"><FileTable files={files} listing={listing} /></div>
    {details.homepage && <div className="container"><a className="btn btn-default space" href={details.homepage}><span className="glyphicon glyphicon-chevron-left" aria-hidden="true" /> {t("返回祭典主页", "ホームページへ戻る")}</a></div>}
    {!!details.information.length && <div className="container" style={{ marginTop: "1em" }}><div className="row"><div className="col-sm-6">
      <h3 className="h4">{details.title}</h3><table className="table"><tbody>{details.information.map(field => {
        const number = field.value.match(/^[\d,]+/)?.[0];
        const value = number && field.label === "ファイル" ? t(`${number} 个文件`, `${number} ファイル`) : number && field.label === "ダウンロード" ? t(`${number} 次下载`, `${number} ダウンロード`) : field.value;
        return <tr key={field.label}><th>{t(labels[field.label] || field.label, field.label)}</th><td>{value}</td></tr>;
      })}</tbody></table>
    </div></div></div>}
  </ArchiveChrome>;
}
