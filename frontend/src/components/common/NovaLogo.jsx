// @ts-nocheck
import { useId } from 'react';

function NovaLogo({
  size = 32,
  textColor = '#111111',
  iconColor = '#1B9DFF',
  accentColor,
  className = '',
  showText = true,
}) {
  const generatedId = useId().replace(/:/g, '');
  const gradientId = `nova-electric-blue-${generatedId}`;
  const resolvedAccent = accentColor || textColor;
  const textScale = size >= 40 ? 0.9 : 0.6;
  const fontSize = Math.round(size * textScale);
  const letterSpacing = `${Math.round(size * 0.05)}px`;

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 80 80"
        fill="none"
        aria-hidden="true"
        focusable="false"
      >
        <defs>
          <linearGradient id={gradientId} x1="18" y1="12" x2="62" y2="68">
            <stop offset="0" stopColor="#63E8FF" />
            <stop offset="0.45" stopColor={iconColor} />
            <stop offset="1" stopColor="#006DFF" />
          </linearGradient>
        </defs>
        <g>
          <path
            d="M40 12 C42.7 26.2 52.1 37.3 66 40 C52.1 42.7 42.7 53.8 40 68 C37.3 53.8 27.9 42.7 14 40 C27.9 37.3 37.3 26.2 40 12 Z"
            fill="none"
            stroke={`url(#${gradientId})`}
            strokeWidth="4.8"
            strokeLinejoin="round"
          />
          <path
            d="M25.5 16 C26.3 20.5 29.5 23.7 34 24.5 C29.5 25.3 26.3 28.5 25.5 33 C24.7 28.5 21.5 25.3 17 24.5 C21.5 23.7 24.7 20.5 25.5 16 Z"
            fill={`url(#${gradientId})`}
          />
          <path
            d="M55.5 49 C56.2 52.9 59.1 55.8 63 56.5 C59.1 57.2 56.2 60.1 55.5 64 C54.8 60.1 51.9 57.2 48 56.5 C51.9 55.8 54.8 52.9 55.5 49 Z"
            fill={`url(#${gradientId})`}
          />
        </g>
      </svg>
      {showText ? (
        <span
          className="font-bold"
          style={{
            color: textColor,
            fontSize,
            lineHeight: 1,
            letterSpacing,
            fontFamily: "'Times New Roman', Times, serif",
          }}
        >
          NOVA <span style={{ color: resolvedAccent }}>AI</span>
        </span>
      ) : null}
    </div>
  );
}

export default NovaLogo;
