// @ts-nocheck
function NovaLogo({
  size = 32,
  textColor = '#111111',
  iconColor = '#1B8FE8',
  accentColor,
  className = '',
}) {
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
        <g transform="translate(40,40)">
          <path
            d="M0,-28 C2,-10 10,-2 28,0 C10,2 2,10 0,28 C-2,10 -10,2 -28,0 C-10,-2 -2,-10 0,-28 Z"
            fill="none"
            stroke={iconColor}
            strokeWidth="4.5"
            strokeLinejoin="round"
          />
          <g transform="translate(-22,-23)">
            <path
              d="M0,-7.5 C0.5,-3 3,-0.5 7.5,0 C3,0.5 0.5,3 0,7.5 C-0.5,3 -3,0.5 -7.5,0 C-3,-0.5 -0.5,-3 0,-7.5 Z"
              fill={iconColor}
            />
          </g>
          <g transform="translate(22,22)">
            <path
              d="M0,-6 C0.4,-2.5 2.5,-0.4 6,0 C2.5,0.4 0.4,2.5 0,6 C-0.4,2.5 -2.5,0.4 -6,0 C-2.5,-0.4 -0.4,-2.5 0,-6 Z"
              fill={iconColor}
            />
          </g>
        </g>
      </svg>
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
    </div>
  );
}

export default NovaLogo;
