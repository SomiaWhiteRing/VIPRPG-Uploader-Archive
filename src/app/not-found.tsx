import Link from "next/link";
import ArchiveChrome from "@/components/archive-chrome";
import { Text } from "@/components/language-context";
import PageMetadata from "@/components/page-metadata";
import { notFoundInfo, staticMetadata } from "@/lib/page-metadata";

export const metadata = staticMetadata(notFoundInfo);

export default function NotFound() {
  return <ArchiveChrome><PageMetadata info={notFoundInfo} /><section className="container"><div className="page-header"><h1><Text zh="未收录此上传区或文件" ja="アップローダーまたはファイルが見つかりません" /></h1></div><p><Text zh="请核对上传区大小写和原文件编号，也可返回目录粘贴原链接重新定位。" ja="アップローダー名（大文字・小文字を含む）と元のファイル番号をご確認ください。アップローダー一覧に戻り、元の URL を入力して探すこともできます。" /></p><Link href="/"><Text zh="返回上传区目录" ja="アップローダー一覧に戻る" /></Link></section></ArchiveChrome>;
}
