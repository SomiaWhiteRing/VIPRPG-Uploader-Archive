import { Fragment } from "react";
import type { RichTextNode } from "@/lib/archive-types";

export default function RichText({ nodes }: { nodes: RichTextNode[] }) {
  return nodes.map((node, index) => {
    if (node.type === "text") return <Fragment key={index}>{node.text}</Fragment>;
    if (node.type === "break") return <br key={index} />;
    if (node.type === "link") return <a key={index} href={node.href}><RichText nodes={node.children} /></a>;
    if (node.type === "strong") return <strong key={index}><RichText nodes={node.children} /></strong>;
    return <em key={index}><RichText nodes={node.children} /></em>;
  });
}
