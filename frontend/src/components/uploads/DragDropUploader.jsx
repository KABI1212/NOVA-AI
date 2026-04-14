import React, { useEffect, useMemo, useState } from "react";
import { FileUp, UploadCloud } from "lucide-react";

export default function DragDropUploader({
  onFilesSelected,
  disabled = false,
  className = "",
  children,
}) {
  const [dragDepth, setDragDepth] = useState(0);
  const dragging = dragDepth > 0 && !disabled;

  useEffect(() => {
    if (disabled) {
      setDragDepth(0);
    }
  }, [disabled]);

  const overlayCopy = useMemo(
    () =>
      dragging ? (
        <div className="pointer-events-none absolute inset-0 z-20 rounded-[28px] border border-dashed border-sky-300/70 bg-slate-950/75 backdrop-blur">
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-slate-50">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-500/15 text-sky-200 shadow-[0_16px_36px_rgba(14,165,233,0.2)]">
              <UploadCloud className="h-8 w-8" />
            </div>
            <div>
              <div className="text-base font-semibold tracking-tight">Drop files to analyze in chat</div>
              <div className="mt-1 text-sm text-slate-300">
                PDFs, docs, spreadsheets, images, code, and notes are supported
              </div>
            </div>
          </div>
        </div>
      ) : null,
    [dragging]
  );

  const handleDrop = (event) => {
    event.preventDefault();
    setDragDepth(0);
    if (disabled) {
      return;
    }
    const selectedFiles = Array.from(event.dataTransfer?.files || []);
    if (selectedFiles.length) {
      onFilesSelected?.(selectedFiles);
    }
  };

  return (
    <div
      className={`relative ${className}`}
      onDragEnter={(event) => {
        event.preventDefault();
        if (!disabled) {
          setDragDepth((current) => current + 1);
        }
      }}
      onDragOver={(event) => {
        event.preventDefault();
        if (event.dataTransfer) {
          event.dataTransfer.dropEffect = "copy";
        }
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        if (event.currentTarget.contains(event.relatedTarget)) {
          return;
        }
        setDragDepth((current) => Math.max(0, current - 1));
      }}
      onDrop={handleDrop}
    >
      {children}
      {overlayCopy}
      {!children ? (
        <div className="rounded-[24px] border border-dashed border-white/15 bg-white/[0.03] px-5 py-6 text-sm text-slate-300">
          <div className="flex items-center gap-3 text-slate-100">
            <FileUp className="h-5 w-5 text-sky-300" />
            <span>Drag files here to add them to the current chat.</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
