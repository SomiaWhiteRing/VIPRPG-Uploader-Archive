import { catalog } from "@/lib/catalog";
import { archive } from "@/lib/archive";
import ArchiveChrome from "@/components/archive-chrome";
import HomeContent from "@/components/home-content";
import PageMetadata from "@/components/page-metadata";
import { homeInfo } from "@/lib/page-metadata";

export default function HomePage() {
  return <ArchiveChrome><PageMetadata info={homeInfo} /><HomeContent groups={catalog.groups.map(group => ({ ...group, title: archive.uploaders[group.slug]?.title || group.slug }))} updatedAt={catalog.updatedAt} /></ArchiveChrome>;
}
