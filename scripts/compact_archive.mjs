import fs from "node:fs";
import { pathToFileURL } from "node:url";

// Only omit values whose existing rendering fallback is identical.
export function compactArchive(archive, catalog) {
  const files = new Map(catalog.files.map(file => [`${file.uploader}/${file.id}`, file]));
  for (const [key, details] of Object.entries(archive.files)) {
    const file = files.get(key);
    for (const [field, base] of [["displayName", "name"], ["original", "name"], ["listedSize", "listedSize"]]) {
      if (details[field] === file[base]) delete details[field];
    }
    if (details.listComment === details.comment) delete details.listComment;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const filename = "src/data/archive.json";
  const archive = JSON.parse(fs.readFileSync(filename, "utf8"));
  const catalog = JSON.parse(fs.readFileSync("src/data/catalog.json", "utf8"));
  compactArchive(archive, catalog);
  fs.writeFileSync(filename, JSON.stringify(archive) + "\n");
}
