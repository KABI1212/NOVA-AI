import React, { useEffect, useMemo } from "react";
import { Download, EyeOff, FileCode2, FileText, Image as ImageIcon } from "lucide-react";

function isImageFile(file) {
  const mimeType = String(file?.mime_type || file?.type || "").toLowerCase();
  const name = String(file?.original_name || file?.name || "").toLowerCase();
  return mimeType.startsWith("image/") || [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"].some((ext) => name.endsWith(ext));
}

function isPdfFile(file) {
  const mimeType = String(file?.mime_type || file?.type || "").toLowerCase();
  const name = String(file?.original_name || file?.name || "").toLowerCase();
  return mimeType.includes("pdf") || name.endsWith(".pdf");
}

function isCodeFile(file) {
  const name = String(file?.original_name || file?.name || "").toLowerCase();
  return [".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".sql", ".html", ".css", ".xml", ".yml", ".yaml"].some((ext) =>
    name.endsWith(ext)
  );
}

function resolveObjectUrl(file) {
  if (file?.objectUrl) {
    return file.objectUrl;
  }
  if (file?.localFile instanceof File) {
    return URL.createObjectURL(file.localFile);
  }
  return "";
}

export default function FilePreviewModal({ file, open, onClose }) {
  const objectUrl = useMemo(() => (open && file ? resolveObjectUrl(file) : ""), [file, open]);

  useEffect(() => {
    return () => {
      if (file?.localFile instanceof File && objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [file, objectUrl]);

  if (!open || !file) {
    return null;
  }

  const previewText = String(file?.preview_text || "").trim();
  const imagePreview = isImageFile(file) && objectUrl;
  const pdfPreview = isPdfFile(file) && objectUrl;
  const codePreview = isCodeFile(file);

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/80 px-4 py-6 backdrop-blur-sm" onClick={onClose}>
      <div
        className="relative flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,#11161c_0%,#0a0d12_100%)] shadow-[0_30px_90px_rgba(0,0,0,0.45)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-4 border-b border-white/8 px-6 py-4">
          <div className="min-w-0">
            <div className="truncate text-base font-semibold tracking-tight text-slate-50">
              {file?.original_name || file?.name || "Preview"}
            </div>
            <div className="mt-1 text-xs text-slate-400">
              {file?.status === "ready" ? "Indexed and ready to chat" : "Previewing current upload"}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {objectUrl ? (
              <a
                href={objectUrl}
                download={file?.original_name || file?.name || "download"}
                className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03] text-slate-200 transition hover:border-sky-300/40 hover:bg-sky-500/10 hover:text-sky-100"
                title="Download preview"
              >
                <Download className="h-4 w-4" />
              </a>
            ) : null}
            <button
              type="button"
              className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03] text-slate-200 transition hover:border-rose-300/40 hover:bg-rose-500/10 hover:text-rose-100"
              onClick={onClose}
              title="Close preview"
            >
              <EyeOff className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-auto p-6">
          {imagePreview ? (
            <div className="overflow-hidden rounded-[28px] border border-white/8 bg-black/30">
              <img src={objectUrl} alt={file?.original_name || "Preview"} className="max-h-[72vh] w-full object-contain" />
            </div>
          ) : null}

          {!imagePreview && pdfPreview ? (
            <div className="overflow-hidden rounded-[28px] border border-white/8 bg-white">
              <iframe title="PDF preview" src={objectUrl} className="h-[72vh] w-full" />
            </div>
          ) : null}

          {!imagePreview && !pdfPreview ? (
            <div className="rounded-[28px] border border-white/8 bg-black/25 p-5">
              <div className="mb-4 flex items-center gap-3 text-slate-200">
                {codePreview ? <FileCode2 className="h-5 w-5 text-sky-300" /> : <FileText className="h-5 w-5 text-sky-300" />}
                <span className="text-sm font-medium">{codePreview ? "Code / text preview" : "Extracted preview"}</span>
              </div>
              <pre className="whitespace-pre-wrap break-words text-sm leading-7 text-slate-200">
                {previewText || "Preview is not available for this file yet."}
              </pre>
            </div>
          ) : null}

          {!imagePreview && !pdfPreview && !previewText ? (
            <div className="mt-4 flex items-center gap-2 text-sm text-slate-400">
              <ImageIcon className="h-4 w-4" />
              <span>The preview will improve once analysis finishes.</span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
