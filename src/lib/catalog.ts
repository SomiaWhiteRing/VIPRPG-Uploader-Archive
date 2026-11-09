import snapshot from "@/data/catalog.json";
import supplementSnapshot from "@/data/supplements.json";
import damagedSnapshot from "@/data/damaged-files.json";
import downloadSnapshot from "@/data/ia-downloads.json";
import storage from "@/data/ia-storage.json";
import aliasSnapshot from "@/data/source-aliases.json";
import { canDownload, type ArchiveFile, type Uploader } from "@/lib/files";
import { excludedUploaders } from "@/lib/uploader-visibility";

const supplements: { releaseUrl: string; files: { uploader: string; id: string; url: string; md5: string; size: number; modified: boolean; releaseUrl?: string }[] } = supplementSnapshot;
const supplementsByKey = new Map(supplements.files.map(file => [`${file.uploader}/${file.id}`, file]));
const damagedFiles = new Set(damagedSnapshot);
const downloads: Record<string, string> = downloadSnapshot;
export const sourceAliases: Record<string, string> = aliasSnapshot;
const snapshotByKey = new Map(snapshot.files.map(file => [`${file.uploader}/${file.id}`, file]));
export const catalog: { updatedAt: string; identifier: string; groups: Uploader[]; files: ArchiveFile[] } = {
  ...snapshot,
  identifier: storage.identifier,
  groups: snapshot.groups.filter(group => !excludedUploaders.has(group.slug)),
  files: snapshot.files.filter(file => !excludedUploaders.has(file.uploader)).map(source => {
    const key = `${source.uploader}/${source.id}`;
    const canonical = sourceAliases[key];
    const file = canonical ? { ...snapshotByKey.get(canonical)!, uploader: source.uploader, sourceUrl: source.sourceUrl } : source;
    if (damagedFiles.has(key)) return { ...file, state: "source_damaged" };
    const supplement = supplementsByKey.get(key);
    if (supplement) return { ...file, supplement: { ...supplement, releaseUrl: supplement.releaseUrl ?? supplements.releaseUrl } };
    const path = downloads[canonical || key];
    if (path) return { ...file, remotePath: path, archiveDownload: { identifier: storage.identifier, path } };
    return file;
  }),
};
export const groupsBySlug = new Map(catalog.groups.map((group) => [group.slug, group]));
export const filesByGroup = new Map<string, ArchiveFile[]>(catalog.groups.map(group => [group.slug, []]));
export const filesByKey = new Map<string, ArchiveFile>();
for (const file of catalog.files) {
  filesByKey.set(`${file.uploader}/${file.id}`, file);
  const group = filesByGroup.get(file.uploader) || [];
  group.push(file);
  filesByGroup.set(file.uploader, group);
}
for (const files of filesByGroup.values()) files.sort((a, b) => Number(b.id) - Number(a.id));
for (const group of catalog.groups) {
  group.counts.available = (filesByGroup.get(group.slug) || []).filter(canDownload).length;
}

