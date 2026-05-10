// @ts-nocheck

const NOVA_WORDMARK_SRC = "/icons/nova-ai-logo.png";
const NOVA_APP_ICON_SRC = "/icons/nova-app-icon.png";

function NovaLogo({
  size = 32,
  className = '',
  showText = true,
}) {
  const imageWidth = Math.round(size * (showText ? 3.1 : 1));
  const imageSrc = showText ? NOVA_WORDMARK_SRC : NOVA_APP_ICON_SRC;

  return (
    <div
      className={`flex items-center gap-2 ${className}`}
      style={{ width: imageWidth, height: size, flexShrink: 0 }}
    >
      <img
        src={imageSrc}
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
