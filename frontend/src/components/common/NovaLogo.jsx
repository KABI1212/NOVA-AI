// @ts-nocheck

const NOVA_LOGO_SRC = "/icons/nova-ai-logo.png";

function NovaLogo({
  size = 32,
  className = '',
  showText = true,
}) {
  const imageWidth = Math.round(size * (showText ? 2.8 : 1.9));

  return (
    <div
      className={`flex items-center gap-2 ${className}`}
      style={{ width: imageWidth, height: size, flexShrink: 0 }}
    >
      <img
        src={NOVA_LOGO_SRC}
        alt="NOVA AI"
        width={imageWidth}
        height={size}
        className="nova-logo-image"
        style={{
          width: imageWidth,
          height: size,
          objectFit: "contain",
          display: "block",
        }}
      />
    </div>
  );
}

export default NovaLogo;
