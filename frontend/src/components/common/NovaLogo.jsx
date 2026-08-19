// @ts-nocheck
import React from 'react';

const NOVA_APP_ICON_SRC = "/icons/nova-app-icon.png";

function NovaLogo({
  size = 32,
  textColor,
  accentColor = '#2563eb',
  className = '',
  showText = true,
}) {
  const textScale = size >= 40 ? 0.85 : 0.68;
  const fontSize = Math.round(size * textScale);

  return (
    <div
      className={`inline-flex items-center gap-2.5 ${className}`}
      style={{ height: size, flexShrink: 0 }}
    >
      <img
        src={NOVA_APP_ICON_SRC}
        alt="NOVA AI"
        width={size}
        height={size}
        className="nova-logo-image object-contain"
        style={{
          width: size,
          height: size,
          display: "block",
          flexShrink: 0,
        }}
      />
      {showText && (
        <span
          className="font-bold tracking-wider select-none leading-none"
          style={{
            fontSize: `${fontSize}px`,
            color: textColor || 'currentColor',
            fontFamily: "'Times New Roman', Times, serif",
          }}
        >
          NOVA <span style={{ color: accentColor }}>AI</span>
        </span>
      )}
    </div>
  );
}

export default NovaLogo;
