import snapshot from "@/data/catalog.json";
import supplementSnapshot from "@/data/supplements.json";
import type { ArchiveFile, Uploader } from "@/lib/files";

const supplements: { releaseUrl: string; files: { uploader: string; id: string; url: string; md5: string; size: number; modified: boolean }[] } = supplementSnapshot;
const supplementsByKey = new Map(supplements.files.map(file => [`${file.uploader}/${file.id}`, file]));
export const catalog: { updatedAt: string; identifier: string; groups: Uploader[]; files: ArchiveFile[] } = {
  ...snapshot,
  files: snapshot.files.map(file => {
    const supplement = supplementsByKey.get(`${file.uploader}/${file.id}`);
    return supplement ? { ...file, supplement: { ...supplement, releaseUrl: supplements.releaseUrl } } : file;
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
  group.counts.available = (filesByGroup.get(group.slug) || []).filter(file => file.supplement || file.state === "indexed").length;
}

