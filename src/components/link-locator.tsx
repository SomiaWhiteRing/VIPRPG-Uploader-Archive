"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLanguage } from "@/components/language-context";

export default function LinkLocator() {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();
  const { t } = useLanguage();
  const messages: Record<string, string> = {
    "请粘贴原 uploader 地址或上传区名称。": "元のアップローダーの URL またはアップローダー名を入力してください。",
    "地址格式有误。": "URL の形式が正しくありません。",
    "请使用 uploader.jp、getuploader.com 或本站的地址。": "uploader.jp、getuploader.com、または当サイトの URL を入力してください。",
    "未识别到上传区或文件编号，请保留原地址中的 /上传区/download/编号。": "アップローダー名またはファイル番号を読み取れませんでした。元の URL の /アップローダー名/download/ファイル番号 の部分を省略せずに入力してください。",
  };
  return <section className="space" aria-label={t("原链接定位", "元の URL から検索")}>
    <form className="archive-form" onSubmit={(event) => {
      event.preventDefault();
      setError("");
      let input = value.trim();
      if (!input) { setError("请粘贴原 uploader 地址或上传区名称。"); return; }
      if (/^(?:(?:u[ux]|www)\.)?(?:getuploader\.com|uploader\.jp)\//i.test(input) || /^uploader\.viprpg\.org\//i.test(input)) input = `https://${input}`;
      let path = input;
      if (/^https?:\/\//i.test(input)) {
        let url: URL;
        try { url = new URL(input); } catch { setError("地址格式有误。"); return; }
        if (!/^(?:[a-z0-9-]+\.)?(?:getuploader\.com|uploader\.jp)$|^uploader\.viprpg\.org$/i.test(url.hostname)) {
          setError("请使用 uploader.jp、getuploader.com 或本站的地址。"); return;
        }
        path = url.pathname;
      }
      const match = path.match(/^\/?([A-Za-z0-9_-]+)(?:\/(?:download\/)?([0-9]+)(?:\/[^?#]*)?)?\/?(?:[?#].*)?$/);
      if (!match) { setError("未识别到上传区或文件编号，请保留原地址中的 /上传区/download/编号。"); return; }
      router.push(`/${match[1]}${match[2] ? `/download/${Number(match[2])}` : ""}`);
    }}>
      <label htmlFor="source-link">{t("通过原链接查找", "元の URL から検索")}</label>
      <div className="input-group"><input className="form-control" id="source-link" type="text" value={value} onChange={(event) => setValue(event.target.value)} placeholder={t("https://ux.getuploader.com/上传区/download/编号", "https://ux.getuploader.com/アップローダー名/download/ファイル番号")} spellCheck={false} aria-describedby={error ? "locator-error" : "locator-hint"} /><span className="input-group-btn"><button className="btn btn-default" type="submit">{t("定位", "開く")}</button></span></div>
      <p className="help-block" id="locator-hint">{t("也可将原地址的域名替换为 ", "元の URL のドメインを ")}<code>uploader.viprpg.org</code>{t("，保留后面的路径直接访问。", " に置き換えるだけでもアクセスできます。ドメインより後ろの部分はそのまま残してください。")}</p>
      {error && <p className="text-danger" id="locator-error" role="alert">{t(error, messages[error] || error)}</p>}
    </form>
  </section>;
}
