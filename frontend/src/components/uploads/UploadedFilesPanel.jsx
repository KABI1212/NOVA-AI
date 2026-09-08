import React from "react";
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

  return (
    <div className="flex flex-wrap items-center gap-2 px-1 py-1 max-w-[820px] mx-auto w-full transition-all duration-200">
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
  );
}
