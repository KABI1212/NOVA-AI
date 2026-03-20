import React from "react";
import { motion } from "framer-motion";

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
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <motion.span
        aria-hidden="true"
        className="absolute inset-0 rounded-[28%] bg-[radial-gradient(circle,rgba(45,212,191,0.42),rgba(34,211,238,0.16),transparent_72%)] blur-md"
        animate={
          animated
            ? {
                scale: [0.82, 1.18, 0.9],
                opacity: [0.25, 0.7, 0.25],
              }
            : {
                scale: 1,
                opacity: 0.28,
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
      />

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
        className="relative flex h-full w-full items-center justify-center rounded-[28%] border border-white/10 bg-[linear-gradient(180deg,rgba(10,22,32,0.96),rgba(6,14,24,0.9))] shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_18px_36px_rgba(3,7,18,0.38)]"
      >
        <svg
          width={size}
          height={size}
          viewBox="0 0 80 80"
          fill="none"
          aria-hidden="true"
          focusable="false"
        >
          <defs>
            <linearGradient id="novaLogoStroke" x1="16" y1="12" x2="64" y2="68" gradientUnits="userSpaceOnUse">
              <stop stopColor="#5eead4" />
              <stop offset="1" stopColor="#67e8f9" />
            </linearGradient>
          </defs>

          <g transform="translate(40,40)">
            <path
              d="M0,-28 C2,-10 10,-2 28,0 C10,2 2,10 0,28 C-2,10 -10,2 -28,0 C-10,-2 -2,-10 0,-28 Z"
              fill="none"
              stroke="url(#novaLogoStroke)"
              strokeWidth="4.5"
              strokeLinejoin="round"
            />
            <circle cx="0" cy="0" r="4.5" fill="#d1fae5" fillOpacity="0.95" />
            <g transform="translate(-22,-23)">
              <path
                d="M0,-7.5 C0.5,-3 3,-0.5 7.5,0 C3,0.5 0.5,3 0,7.5 C-0.5,3 -3,0.5 -7.5,0 C-3,-0.5 -0.5,-3 0,-7.5 Z"
                fill="#5eead4"
              />
            </g>
            <g transform="translate(22,22)">
              <path
                d="M0,-6 C0.4,-2.5 2.5,-0.4 6,0 C2.5,0.4 0.4,2.5 0,6 C-0.4,2.5 -2.5,0.4 -6,0 C-2.5,-0.4 -0.4,-2.5 0,-6 Z"
                fill="#67e8f9"
              />
            </g>
          </g>
        </svg>
      </motion.div>
    </div>
  );

  if (!showText) {
    return <div className={className}>{icon}</div>;
  }

  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      {icon}
      <div className="font-display text-[11px] font-semibold uppercase tracking-[0.3em] text-white">
        NOVA <span className="text-[#5eead4]">AI</span>
      </div>
    </div>
  );
}
