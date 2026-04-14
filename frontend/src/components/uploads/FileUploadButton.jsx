import React, { useRef } from "react";
import { Paperclip } from "lucide-react";

export default function FileUploadButton({
  onSelectFiles,
  disabled = false,
  accept = "",
  multiple = true,
  className = "",
  title = "Upload files",
}) {
  const inputRef = useRef(null);

  const handleChange = (event) => {
    const selectedFiles = Array.from(event.target.files || []);
    if (selectedFiles.length) {
      onSelectFiles?.(selectedFiles);
    }
    event.target.value = "";
  };

  return (
    <>
      <button
        type="button"
        title={title}
        aria-label={title}
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        className={className}
      >
        <Paperclip className="h-4 w-4" />
      </button>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        multiple={multiple}
        accept={accept}
        onChange={handleChange}
      />
    </>
  );
}
