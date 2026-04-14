import React from "react";
import { FileStack } from "lucide-react";

import FileCard from "./FileCard";

export default function UploadedFilesPanel({
  files = [],
  onPreview,
  onRetry,
  onRemove,
  disabled = false,
}) {
  if (!files.length) {
    return null;
  }

  const readyCount = files.filter((file) => file?.status === "ready").length;
  const pendingCount = files.filter(
    (file) => file?.status && !["ready", "failed", "failed-upload"].includes(file.status)
  ).length;

  return (
    <section className="mx-auto w-full max-w-[980px] rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(17,20,24,0.94)_0%,rgba(10,13,17,0.94)_100%)] p-4 shadow-[0_22px_52px_rgba(0,0,0,0.26)]">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-500/12 text-sky-200">
            <FileStack className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight text-slate-50">Session files</div>
            <div className="text-xs text-slate-400">
              {readyCount} ready{pendingCount ? `, ${pendingCount} still analyzing` : ""}
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {files.map((file) => (
          <FileCard
            key={file.id || file.clientId}
            file={file}
            onPreview={onPreview}
            onRetry={onRetry}
            onRemove={onRemove}
            disabled={disabled}
          />
        ))}
      </div>
    </section>
  );
}
