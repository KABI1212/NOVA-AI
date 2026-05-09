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
    <section className="mx-auto w-full max-w-[820px] rounded-2xl border border-white/10 bg-black/40 p-3 shadow-none">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/5 text-slate-300">
            <FileStack className="h-4 w-4" />
          </div>
          <div>
            <div className="text-[13px] font-semibold tracking-tight text-slate-50">Session files</div>
            <div className="text-[11px] text-slate-400">
              {readyCount} ready{pendingCount ? `, ${pendingCount} still analyzing` : ""}
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-2">
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
