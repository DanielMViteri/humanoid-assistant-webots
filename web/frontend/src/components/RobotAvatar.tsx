export function RobotAvatar({ size = 96, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      className={className}
      role="img"
      aria-label="Nesto robot"
    >
      {/* antenna */}
      <line x1="60" y1="14" x2="60" y2="26" stroke="#1f7d57" strokeWidth="3" strokeLinecap="round" />
      <circle cx="60" cy="12" r="4" fill="#1f7d57" />
      {/* ears */}
      <rect x="14" y="44" width="14" height="28" rx="7" fill="#8fc4ab" />
      <rect x="92" y="44" width="14" height="28" rx="7" fill="#8fc4ab" />
      {/* head */}
      <rect x="24" y="30" width="72" height="56" rx="20" fill="#ffffff" stroke="#cfe2d6" strokeWidth="3" />
      {/* face screen */}
      <rect x="33" y="40" width="54" height="36" rx="14" fill="#14302a" />
      {/* eyes + smile */}
      <circle cx="49" cy="56" r="4.5" fill="#7ff0c0" />
      <circle cx="71" cy="56" r="4.5" fill="#7ff0c0" />
      <path d="M50 66 Q60 72 70 66" stroke="#7ff0c0" strokeWidth="3" strokeLinecap="round" fill="none" />
      {/* body */}
      <rect x="34" y="88" width="52" height="24" rx="12" fill="#ffffff" stroke="#cfe2d6" strokeWidth="3" />
      <circle cx="60" cy="100" r="5" fill="#8fc4ab" />
    </svg>
  );
}
