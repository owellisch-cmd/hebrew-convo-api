export default function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <defs>
        <linearGradient id="planwiseShield" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#34d399" />
          <stop offset="100%" stopColor="#0f5c4a" />
        </linearGradient>
      </defs>
      <path
        d="M12 1.4 L21 5.2 V11.2 C21 17.1 17.1 21.9 12 23.4 C6.9 21.9 3 17.1 3 11.2 V5.2 Z"
        fill="url(#planwiseShield)"
      />
      <path
        d="M8 12.1 L10.6 14.7 L16.2 8.9"
        fill="none"
        stroke="#ffffff"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
