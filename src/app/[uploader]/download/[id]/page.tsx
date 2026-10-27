import { notFound } from "next/navigation";
import { catalog, filesByKey, groupsBySlug } from "@/lib/catalog";
import { archive } from "@/lib/archive";
import FileView from "@/components/file-view";
import PageMetadata from "@/components/page-metadata";
import { fileInfo, staticMetadata } from "@/lib/page-metadata";

export const dynamicParams = false;
export function generateStaticParams() {
  return catalog.files.map(file => ({ uploader: file.uploader, id: file.id }));
}
type Props = { params: Promise<{ uploader: string; id: string }> };
export async function generateMetadata({ params }: Props) {
  const { uploader, id } = await params;
  return staticMetadata(fileInfo(filesByKey.get(`${uploader}/${id}`)?.name, id, archive.uploaders[uploader]?.title || uploader));
}
export default async function FilePage({ params }: Props) {
  const { uploader, id } = await params;
  const file = filesByKey.get(`${uploader}/${id}`);
  if (!file) notFound();
  const title = archive.uploaders[uploader]?.title || uploader;
  return <><PageMetadata info={fileInfo(file.name, id, title)} /><FileView file={file} details={archive.files[`${uploader}/${id}`]} uploaderTitle={title} uploaderAvailable={groupsBySlug.has(uploader)} /></>;
}
