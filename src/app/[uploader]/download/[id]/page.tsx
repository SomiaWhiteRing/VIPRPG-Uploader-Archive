import { notFound } from "next/navigation";
import { catalog, filesByKey, groupsBySlug, sourceAliases } from "@/lib/catalog";
import { archive } from "@/lib/archive";
import FileView from "@/components/file-view";
import PageMetadata from "@/components/page-metadata";
import { fileInfo } from "@/lib/page-metadata";
import originalTitles from "@/data/original-titles.json";

export const dynamicParams = false;
export function generateStaticParams() {
  return catalog.files.map(file => ({ uploader: file.uploader, id: file.id }));
}
type Props = { params: Promise<{ uploader: string; id: string }> };
export default async function FilePage({ params }: Props) {
  const { uploader, id } = await params;
  const key = sourceAliases[`${uploader}/${id}`] || `${uploader}/${id}`;
  const file = filesByKey.get(key);
  if (!file) notFound();
  const title = archive.uploaders[file.uploader]?.title || file.uploader;
  const details = archive.files[key];
  const originalTitle = (originalTitles as Record<string, string>)[`/${uploader}/download/${id}`];
  return <><PageMetadata info={fileInfo(file.name, id, title, details?.displayName, details?.original, originalTitle)} /><FileView file={file} details={details} uploaderTitle={title} uploaderAvailable={groupsBySlug.has(file.uploader)} /></>;
}
