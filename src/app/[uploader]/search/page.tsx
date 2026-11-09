import { notFound } from "next/navigation";
import { catalog } from "@/lib/catalog";
import { archive, tableFilesByGroup } from "@/lib/archive";
import ArchiveChrome from "@/components/archive-chrome";
import FileTable from "@/components/file-table";
import PageMetadata from "@/components/page-metadata";
import { searchInfo } from "@/lib/page-metadata";
import { linkOnlyUploaders } from "@/lib/uploader-visibility";
import originalTitles from "@/data/original-titles.json";

export const dynamicParams = false;
export function generateStaticParams() {
  return catalog.groups.filter(group => !linkOnlyUploaders.has(group.slug)).map(group => ({ uploader: group.slug }));
}
export default async function SearchPage({ params }: { params: Promise<{ uploader: string }> }) {
  const { uploader } = await params;
  const files = tableFilesByGroup.get(uploader);
  if (!files || linkOnlyUploaders.has(uploader)) notFound();
  const title = archive.uploaders[uploader]?.title || uploader;
  const originalTitle = (originalTitles as Record<string, string>)[`/${uploader}`];
  return <ArchiveChrome title={title} slug={uploader}><div className="container">
    <PageMetadata info={searchInfo(title, originalTitle)} />
    <div className="page-header"><h1>{title} <small>uploader.jp</small></h1></div>
    <FileTable files={files} />
  </div></ArchiveChrome>;
}
