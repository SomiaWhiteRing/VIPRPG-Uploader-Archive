import { notFound } from "next/navigation";
import { catalog, groupsBySlug } from "@/lib/catalog";
import { archive, getListing, getListingFiles } from "@/lib/archive";
import UploaderView from "@/components/uploader-view";
import PageMetadata from "@/components/page-metadata";
import { uploaderInfo } from "@/lib/page-metadata";

export const dynamicParams = false;
export function generateStaticParams() {
  return catalog.groups.map(group => ({ uploader: group.slug }));
}
export default async function UploaderPage({ params }: { params: Promise<{ uploader: string }> }) {
  const { uploader } = await params;
  if (!groupsBySlug.has(uploader)) notFound();
  const details = archive.uploaders[uploader];
  const listing = getListing(`/${uploader}`)!;
  return <><PageMetadata info={uploaderInfo(details.title)} /><UploaderView slug={uploader} details={details} listing={listing} files={getListingFiles(listing)} /></>;
}
