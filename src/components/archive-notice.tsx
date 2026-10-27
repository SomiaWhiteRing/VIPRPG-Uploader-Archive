"use client";

import { useLayoutEffect, useState } from "react";
import { useLanguage } from "@/components/language-context";

const STORAGE_KEY = "uploader-archive-notice-dismissed-v1";

export default function ArchiveNotice() {
  const [visible, setVisible] = useState(true);
  const { t } = useLanguage();
  useLayoutEffect(() => { setVisible(localStorage.getItem(STORAGE_KEY) !== "1"); }, []);
  if (!visible) return null;
  return <div className="container"><div className="alert alert-info alert-dismissible" role="note">
    <button type="button" className="close" aria-label={t("关闭通知", "通知を閉じる")} onClick={() => {
      localStorage.setItem(STORAGE_KEY, "1");
      setVisible(false);
    }}><span aria-hidden="true">×</span></button>
    <span className="glyphicon glyphicon-info-sign" aria-hidden="true" />{" "}
    {t("当前页面的信息为归档时的固定数据，不会实时更新。需要密码的文件未保存。", "このページにはアーカイブ時点の情報を表示しています。リアルタイムでは更新されません。ダウンロードにパスワードが必要なファイルは保存していません。")}
  </div></div>;
}
