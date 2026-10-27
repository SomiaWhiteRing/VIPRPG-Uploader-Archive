import { notFound } from "next/navigation";
import UploaderView from "@/components/uploader-view";
import { archive, getListing, getListingFiles } from "@/lib/archive";
import { catalog } from "@/lib/catalog";
import PageMetadata from "@/components/page-metadata";
import { staticMetadata, uploaderInfo } from "@/lib/page-metadata";

export const dynamicParams = false;
export function generateStaticParams() {
  const routes = new Set([...Object.keys(archive.listings).filter(route => route.includes("/index/")), ...catalog.groups.map(group => `/${group.slug}/index/date/desc/1`)]);
  return [...routes].map(route => {
    const [uploader, ...path] = route.slice(1).split("/");
    return { uploader, path };
  });
}
type Props = { params: Promise<{ uploader: string; path: string[] }> };
export async function generateMetadata({ params }: Props) {
  const { uploader, path } = await params;
  return staticMetadata(uploaderInfo(archive.uploaders[uploader]?.title || uploader, path.at(-1)));
}
export default async function ListingPage({ params }: Props) {
  const { uploader, path } = await params;
  const listing = getListing(`/${uploader}/${path.join("/")}`);
  if (!listing) notFound();
  const details = archive.uploaders[uploader];
  return <><PageMetadata info={uploaderInfo(details.title, String(listing.page))} /><UploaderView slug={uploader} details={details} listing={listing} files={getListingFiles(listing)} /></>;
}
