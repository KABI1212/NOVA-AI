import React from "react";
import {
  AlertCircle,
  Eye,
  FileCode2,
  FileSpreadsheet,
  FileText,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  X,
} from "lucide-react";

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

export default function FileCard({ file, onPreview, onRetry, onRemove, disabled = false }) {
  const Icon = resolveIcon(file);
  const status = String(file?.status || "").toLowerCase();
  const fileName = file?.original_name || file?.name || "Document";
  const isFailed = status === "failed" || status === "failed-upload";
  const isReady = status === "ready";

  // 1. Ready State: Collapse into a sleek dismissible chip (ChatGPT / Claude style pill)
  if (isReady) {
    return (
      <div className="group relative inline-flex items-center gap-2 rounded-xl border border-white/10 bg-slate-900/90 px-3 py-1.5 backdrop-blur-md transition-all hover:border-white/20 hover:bg-slate-800/90 shadow-sm animate-in fade-in zoom-in-95 duration-200">
        <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-lg bg-white/5 text-sky-400">
          <Icon className="h-3.5 w-3.5" />
        </div>

        <div className="flex items-baseline gap-1.5 min-w-0">
          <span className="truncate max-w-[170px] sm:max-w-[240px] text-xs font-medium text-slate-100" title={fileName}>
            {fileName}
          </span>
          <span className="text-[10px] text-slate-400 flex-shrink-0">{formatFileSize(file?.size)}</span>
        </div>

        <div className="flex items-center gap-0.5 ml-1">
          {onPreview ? (
            <button
              type="button"
              className="flex h-5 w-5 items-center justify-center rounded-md text-slate-400 transition hover:bg-white/10 hover:text-slate-100 disabled:opacity-40"
              onClick={() => onPreview(file)}
              disabled={disabled}
              title="Inspect preview"
              aria-label="Inspect preview"
            >
              <Eye className="h-3 w-3" />
            </button>
          ) : null}
          <button
            type="button"
            className="flex h-5 w-5 items-center justify-center rounded-md text-slate-400 transition hover:bg-rose-500/20 hover:text-rose-300 disabled:opacity-40"
            onClick={() => onRemove?.(file)}
            disabled={disabled}
            title="Remove attachment"
            aria-label="Remove attachment"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    );
  }

  // 2. Failed State: Compact chip with retry & remove
  if (isFailed) {
    const errorText = file?.error || "Processing failed";
    return (
      <div className="relative inline-flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-950/40 px-3 py-1.5 text-xs text-rose-200 shadow-sm backdrop-blur-md max-w-[340px] animate-in fade-in duration-200">
        <AlertCircle className="h-4 w-4 flex-shrink-0 text-rose-400" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-xs font-medium text-rose-100" title={fileName}>
            {fileName}
          </div>
          <div className="truncate text-[10px] text-rose-300/80" title={errorText}>
            {errorText}
          </div>
        </div>
        {onRetry ? (
          <button
            type="button"
            className="flex h-5 w-5 items-center justify-center rounded-md text-amber-300 transition hover:bg-amber-500/20"
            onClick={() => onRetry(file)}
            disabled={disabled}
            title="Retry"
            aria-label="Retry"
          >
            <RefreshCw className="h-3 w-3" />
          </button>
        ) : null}
        <button
          type="button"
          className="flex h-5 w-5 items-center justify-center rounded-md text-rose-300 transition hover:bg-rose-500/20"
          onClick={() => onRemove?.(file)}
          disabled={disabled}
          title="Remove"
          aria-label="Remove"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  // 3. Uploading / In-Progress State: Compact card with slim progress indicator
  const progress = Number(file?.progress?.progress ?? 0);
  const message =
    file?.progress?.message || (status === "uploading" ? `Uploading ${progress}%` : "Analyzing...");

  return (
    <div className="relative flex items-center gap-2.5 rounded-xl border border-sky-500/20 bg-slate-900/90 px-3 py-2 text-xs text-slate-200 shadow-sm backdrop-blur-md min-w-[200px] max-w-[300px] overflow-hidden animate-in fade-in duration-200">
      <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-sky-500/10 text-sky-400">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="truncate text-xs font-medium text-slate-100" title={fileName}>
          {fileName}
        </div>
        <div className="text-[10px] text-sky-300/80 truncate">
          {message}
        </div>
      </div>

      <button
        type="button"
        className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-md text-slate-400 transition hover:bg-white/10 hover:text-slate-200 disabled:opacity-40"
        onClick={() => onRemove?.(file)}
        disabled={disabled}
        title="Cancel"
        aria-label="Cancel upload"
      >
        <X className="h-3.5 w-3.5" />
      </button>

      {/* Slim progress bar pinned to the bottom */}
      <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-white/10">
        <div
          className="h-full bg-gradient-to-r from-sky-400 to-indigo-400 transition-all duration-300 ease-out"
          style={{ width: `${Math.max(5, Math.min(progress, 100))}%` }}
        />
      </div>
    </div>
  );
}
