import { archive, tableFilesByGroup } from "@/lib/archive";
import { linkOnlyUploaders } from "@/lib/uploader-visibility";

export const dynamic = "force-static";

export function GET() {
  return Response.json([...tableFilesByGroup.entries()]
    .filter(([slug]) => !linkOnlyUploaders.has(slug))
    .flatMap(([slug, files]) => files.map(file => ({ ...file, uploaderTitle: archive.uploaders[slug]?.title || slug })))
  );
}
