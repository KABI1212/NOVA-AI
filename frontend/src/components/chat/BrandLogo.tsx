import { motion } from "framer-motion";

import NovaLogo from "../common/NovaLogo";

interface BrandLogoProps {
  size?: number;
  showText?: boolean;
  animated?: boolean;
  className?: string;
}

export default function BrandLogo({
  size = 34,
  showText = false,
  animated = false,
  className = "",
}: BrandLogoProps) {
  const icon = (
    <motion.div
      animate={
        animated
          ? {
              scale: [1, 1.04, 1],
              y: [0, -1, 0],
            }
          : {
              scale: 1,
              y: 0,
            }
      }
      transition={
        animated
          ? {
              duration: 1.2,
              repeat: Number.POSITIVE_INFINITY,
              ease: "easeInOut",
            }
          : { duration: 0.2 }
      }
    >
      <NovaLogo size={size} showText={false} />
    </motion.div>
  );

  if (!showText) {
    return <div className={className}>{icon}</div>;
  }

  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      {icon}
      <div className="font-display text-[11px] font-semibold uppercase tracking-[0.3em] text-white">
        NOVA <span className="text-[#1B9DFF]">AI</span>
      </div>
    </div>
  );
}
