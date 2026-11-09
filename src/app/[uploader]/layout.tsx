import type { Metadata } from "next";
import { linkOnlyUploaders } from "@/lib/uploader-visibility";

export async function generateMetadata({ params }: { params: Promise<{ uploader: string }> }): Promise<Metadata> {
  const { uploader } = await params;
  return linkOnlyUploaders.has(uploader) ? { robots: { index: false } } : {};
}

export default function UploaderLayout({ children }: { children: React.ReactNode }) {
  return children;
}
