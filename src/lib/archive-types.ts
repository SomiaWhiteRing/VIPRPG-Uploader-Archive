export type RichTextNode =
  | { type: "text"; text: string }
  | { type: "break" }
  | { type: "link"; href: string; children: RichTextNode[] }
  | { type: "strong" | "em"; children: RichTextNode[] };

export interface UploaderDetails {
  title: string;
  description: RichTextNode[];
  information: { label: string; value: string }[];
  homepage: string | null;
}
export interface FileDetails {
  displayName?: string;
  comment?: string;
  listComment?: string;
  original?: string;
  listedSize?: string | null;
  fullDate?: string | null;
  counter: string | null;
  md5?: string | null;
  hasDetail: boolean;
}
export interface Listing {
  uploader: string;
  page: number;
  ids: string[];
  pagination: { page: number; kind: "previous" | "next" | "page"; active: boolean }[];
}
export interface ArchiveData {
  uploaders: Record<string, UploaderDetails>;
  files: Partial<Record<string, FileDetails>>;
  listings: Record<string, Listing>;
}
