type Props = { pose?: "wave" | "idle"; className?: string };

export default function Mascot({ pose = "wave", className = "" }: Props) {
  return (
    <svg viewBox="0 0 170 180" className={`mascot-bob ${className}`} role="img" aria-label="Sabi, tu mesonero en WhatsApp">
      <ellipse cx="82" cy="172" rx="40" ry="5" fill="#000" opacity=".18" />
      <g className={pose === "wave" ? "mascot-wave" : undefined}>
        <path d="M134 84c10-10 16-24 14-40" stroke="#1fb458" strokeWidth="13" strokeLinecap="round" fill="none" />
        <circle cx="148" cy="40" r="10" fill="#25D366" />
      </g>
      <path d="M30 104c-8 6-12 16-10 26" stroke="#1fb458" strokeWidth="13" strokeLinecap="round" fill="none" />
      <g transform="rotate(-10 26 134)">
        <rect x="10" y="118" width="30" height="36" rx="4" fill="#fff" />
        <path d="M16 128h18M16 136h18M16 144h11" stroke="#9ca3af" strokeWidth="2.4" strokeLinecap="round" />
      </g>
      <path d="M82 20c-37 0-63 25-63 60 0 20 9 37 25 47l-7 24 25-13c6 2 13 3 20 3 37 0 63-26 63-61S119 20 82 20z" fill="#25D366" />
      <path d="M48 46c9-10 21-15 34-15" stroke="#fff" strokeOpacity=".45" strokeWidth="6" strokeLinecap="round" fill="none" />
      <g className="mascot-blink">
        <ellipse cx="64" cy="74" rx="7" ry="9" fill="#06281e" />
        <ellipse cx="100" cy="74" rx="7" ry="9" fill="#06281e" />
        <circle cx="66.5" cy="70.5" r="2.4" fill="#fff" />
        <circle cx="102.5" cy="70.5" r="2.4" fill="#fff" />
      </g>
      <circle cx="50" cy="92" r="7" fill="#ff8fa3" opacity=".55" />
      <circle cx="114" cy="92" r="7" fill="#ff8fa3" opacity=".55" />
      <path d="M68 94q14 13 28 0" stroke="#06281e" strokeWidth="4.5" strokeLinecap="round" fill="none" />
      <path d="M82 126l-15-8v16zM82 126l15-8v16z" fill="#06281e" />
      <circle cx="82" cy="126" r="3.5" fill="#06281e" />
    </svg>
  );
}
