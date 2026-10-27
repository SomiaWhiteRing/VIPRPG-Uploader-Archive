import data from "@/data/archive.json";
import type { ArchiveData, Listing } from "@/lib/archive-types";
import { catalog, filesByGroup } from "@/lib/catalog";
import type { ListedFile } from "@/lib/files";

export const archive = data as ArchiveData;
const tableFilesByKey = new Map<string, ListedFile>();
for (const file of catalog.files) {
  const key = `${file.uploader}/${file.id}`;
  const merged = { ...file, ...archive.files[key] };
  tableFilesByKey.set(key, {
    uploader: merged.uploader, id: merged.id, name: merged.name,
    listedSize: merged.listedSize, date: merged.date, size: merged.size, localState: merged.localState,
    displayName: merged.displayName, comment: merged.comment, listComment: merged.listComment,
    original: merged.original, counter: merged.counter,
  });
}
export const tableFilesByGroup = new Map([...filesByGroup].map(([slug, files]) => [slug, files.map(file => tableFilesByKey.get(`${slug}/${file.id}`)!)]));
export function getListingFiles(listing: Listing) {
  return listing.ids.map(id => tableFilesByKey.get(`${listing.uploader}/${id}`)!);
}
export function getListing(route: string) {
  return archive.listings[route] || (route.endsWith("/index/date/desc/1") ? archive.listings[route.replace(/\/index\/date\/desc\/1$/, "")] : undefined);
}
