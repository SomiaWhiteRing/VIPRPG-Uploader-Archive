"use client";

import Directory from "@/components/directory";
import LinkLocator from "@/components/link-locator";
import { useLanguage } from "@/components/language-context";
import type { Uploader } from "@/lib/files";

export default function HomeContent({ groups, updatedAt }: { groups: (Uploader & { title: string })[]; updatedAt: string }) {
  const { t } = useLanguage();
  return <div className="container homepage">
    <div className="page-header"><h1>{t("VIPRPG 上传区保存库", "VIPRPG アップローダー保存庫")} <small>uploader.jp</small></h1>
    </div>
    <div className="well well-sm"><LinkLocator /></div>
    <Directory groups={groups} />
    <p className="text-muted space">{t("索引快照：", "インデックス取得日時：")}{updatedAt.slice(0, 19).replace("T", " ")} UTC。{t("上传状态随静态发布更新。", "ファイルの公開状況は、サイト更新時に反映されます。")}</p>
  </div>;
}
