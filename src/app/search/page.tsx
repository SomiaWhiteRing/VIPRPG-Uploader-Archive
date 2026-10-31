import ArchiveChrome from "@/components/archive-chrome";
import GlobalFileSearch from "@/components/global-file-search";
import PageMetadata from "@/components/page-metadata";
import { globalSearchInfo } from "@/lib/page-metadata";

export default function SearchPage() {
  return <ArchiveChrome><PageMetadata info={globalSearchInfo} /><GlobalFileSearch /></ArchiveChrome>;
}
