import { archive, tableFilesByGroup } from "@/lib/archive";

export const dynamic = "force-static";

export function GET() {
  return Response.json([...tableFilesByGroup.entries()].flatMap(([slug, files]) =>
    files.map(file => ({ ...file, uploaderTitle: archive.uploaders[slug]?.title || slug }))
  ));
}
