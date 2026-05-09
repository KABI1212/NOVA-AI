import React from "react";
import {
  AlertCircle,
  Eye,
  FileCode2,
  FileSpreadsheet,
  FileText,
  Image as ImageIcon,
  RefreshCw,
  Trash2,
} from "lucide-react";

import UploadProgressBar from "./UploadProgressBar";

const IMAGE_TYPES = ["image/", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"];

function isImageFile(file) {
  const mimeType = String(file?.mime_type || file?.type || "").toLowerCase();
  const name = String(file?.original_name || file?.name || "").toLowerCase();
  return IMAGE_TYPES.some((value) => mimeType.startsWith(value) || name.endsWith(value));
}

function resolveIcon(file) {
  const name = String(file?.original_name || file?.name || "").toLowerCase();
  if (isImageFile(file)) {
    return ImageIcon;
  }
  if (name.endsWith(".csv") || name.endsWith(".xlsx") || name.endsWith(".xls") || name.endsWith(".xlsm")) {
    return FileSpreadsheet;
  }
  if (
    name.endsWith(".py") ||
    name.endsWith(".js") ||
    name.endsWith(".jsx") ||
    name.endsWith(".ts") ||
    name.endsWith(".tsx") ||
    name.endsWith(".json") ||
    name.endsWith(".sql")
  ) {
    return FileCode2;
  }
  return FileText;
}

function formatFileSize(size) {
  const numeric = Number(size || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return "0 KB";
  }
  if (numeric < 1024 * 1024) {
    return `${(numeric / 1024).toFixed(1)} KB`;
  }
  return `${(numeric / (1024 * 1024)).toFixed(2)} MB`;
}

function statusTone(status) {
  if (status === "ready") {
    return "success";
  }
  if (status === "failed" || status === "failed-upload") {
    return "error";
  }
  return "default";
}

function statusLabel(file) {
  const status = String(file?.status || "").toLowerCase();
  if (status === "ready") {
    return "Ready to chat";
  }
  if (status === "failed" || status === "failed-upload") {
    return file?.error || "Upload failed";
  }
  const progressMessage = String(file?.progress?.message || "").trim();
  return progressMessage || "Analyzing...";
}

export default function FileCard({ file, onPreview, onRetry, onRemove, disabled = false }) {
  const Icon = resolveIcon(file);
  const progress = Number(file?.progress?.progress ?? (file?.status === "ready" ? 100 : 0));
  const tone = statusTone(file?.status);
  const canRetry = file?.status === "failed" || file?.status === "failed-upload";

  return (
    <div className="group rounded-2xl border border-white/10 bg-white/[0.025] p-3 shadow-none transition-colors duration-150 hover:bg-white/[0.04]">
      <div className="flex items-start gap-2.5">
        <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl bg-white/5 text-slate-300">
          <Icon className="h-4 w-4" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate text-[13px] font-semibold tracking-tight text-slate-50">
                {file?.original_name || file?.name || "Untitled file"}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400">
                <span>{formatFileSize(file?.size)}</span>
                <span className="rounded-full border border-white/10 px-1.5 py-0.5 uppercase tracking-[0.14em] text-[9px] text-slate-300">
                  {String(file?.status || "queued").replace(/-/g, " ")}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 bg-transparent text-slate-300 transition hover:border-sky-300/30 hover:bg-sky-500/10 hover:text-sky-100 disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => onPreview?.(file)}
                disabled={disabled}
                aria-label="Preview file"
                title="Preview"
              >
                <Eye className="h-3.5 w-3.5" />
              </button>
              {canRetry ? (
                <button
                  type="button"
                  className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 bg-transparent text-amber-300 transition hover:border-amber-300/30 hover:bg-amber-500/10 hover:text-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={() => onRetry?.(file)}
                  disabled={disabled}
                  aria-label="Retry upload"
                  title="Retry"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                </button>
              ) : null}
              <button
                type="button"
                className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 bg-transparent text-slate-300 transition hover:border-rose-300/30 hover:bg-rose-500/10 hover:text-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => onRemove?.(file)}
                disabled={disabled}
                aria-label="Remove file"
                title="Remove"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          <div className="mt-2 space-y-1.5">
            <UploadProgressBar progress={progress} tone={tone} />
            <div className="flex items-center gap-1.5 text-[11px] text-slate-300">
              {tone === "error" ? <AlertCircle className="h-3.5 w-3.5 text-rose-300" /> : null}
              <span>{statusLabel(file)}</span>
            </div>
          </div>

          {file?.preview_text ? (
            <div className="mt-2 line-clamp-2 rounded-xl border border-white/8 bg-black/20 px-2.5 py-2 text-[11px] leading-4 text-slate-300">
              {file.preview_text}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
