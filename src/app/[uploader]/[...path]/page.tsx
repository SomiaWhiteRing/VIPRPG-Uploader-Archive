import { notFound } from "next/navigation";
import UploaderView from "@/components/uploader-view";
import { archive, getListing, getListingFiles } from "@/lib/archive";
import { catalog, groupsBySlug } from "@/lib/catalog";
import PageMetadata from "@/components/page-metadata";
import { uploaderInfo } from "@/lib/page-metadata";
import originalTitles from "@/data/original-titles.json";

export const dynamicParams = false;
export function generateStaticParams() {
  const listings = Object.entries(archive.listings)
    .filter(([route, listing]) => route.includes("/index/") && groupsBySlug.has(listing.uploader))
    .map(([route]) => route);
  const routes = new Set([...listings, ...catalog.groups.map(group => `/${group.slug}/index/date/desc/1`)]);
  return [...routes].map(route => {
    const [uploader, ...path] = route.slice(1).split("/");
    return { uploader, path };
  });
}
type Props = { params: Promise<{ uploader: string; path: string[] }> };
export default async function ListingPage({ params }: Props) {
  const { uploader, path } = await params;
  if (!groupsBySlug.has(uploader)) notFound();
  const listing = getListing(`/${uploader}/${path.join("/")}`);
  if (!listing) notFound();
  const details = archive.uploaders[uploader];
  const titles = originalTitles as Record<string, string>;
  const originalTitle = titles[`/${uploader}/${path.join("/")}`] || titles[`/${uploader}`];
  return <><PageMetadata info={uploaderInfo(details.title, String(listing.page), originalTitle)} /><UploaderView slug={uploader} details={details} listing={listing} files={getListingFiles(listing)} /></>;
}
