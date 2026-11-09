import { catalog } from "@/lib/catalog";
import { archive } from "@/lib/archive";
import ArchiveChrome from "@/components/archive-chrome";
import HomeContent from "@/components/home-content";
import PageMetadata from "@/components/page-metadata";
import { homeInfo } from "@/lib/page-metadata";
import { linkOnlyUploaders } from "@/lib/uploader-visibility";

export default function HomePage() {
  const groups = catalog.groups.filter(group => !linkOnlyUploaders.has(group.slug))
    .map(group => ({ ...group, title: archive.uploaders[group.slug]?.title || group.slug }));
  return <ArchiveChrome><PageMetadata info={homeInfo} /><HomeContent groups={groups} updatedAt={catalog.updatedAt} /></ArchiveChrome>;
}
