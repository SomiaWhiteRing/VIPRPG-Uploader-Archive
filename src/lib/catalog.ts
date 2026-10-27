import snapshot from "@/data/catalog.json";
import type { ArchiveFile, Uploader } from "@/lib/files";

export const catalog: { updatedAt: string; identifier: string; groups: Uploader[]; files: ArchiveFile[] } = snapshot;
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

