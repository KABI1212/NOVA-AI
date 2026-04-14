import React from "react";

export default function UploadProgressBar({ progress = 0, tone = "default" }) {
  const safeProgress = Math.max(0, Math.min(Number(progress) || 0, 100));
  const toneClass =
    tone === "error"
      ? "bg-rose-500"
      : tone === "success"
        ? "bg-emerald-500"
        : "bg-sky-500";

  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
      <div
        className={`h-full rounded-full transition-all duration-300 ease-out ${toneClass}`}
        style={{ width: `${safeProgress}%` }}
      />
    </div>
  );
}
