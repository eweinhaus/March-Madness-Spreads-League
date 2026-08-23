import { useSportConfig } from '../sportConfig';

/**
 * Sport-specific spinner icons.
 * Inlined SVG to avoid Vercel SPA rewrite issues.
 */

function BasketballSpinnerIcon({ size = 56 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className="picks-check-spin"
    >
      <circle cx="16" cy="16" r="15" fill="#FF6B00" stroke="#000" strokeWidth="2" />
      <path
        d="M16 1C7.716 1 1 7.716 1 16s6.716 15 15 15 15-6.716 15-15S24.284 1 16 1z"
        stroke="#000"
        strokeWidth="2"
      />
      <path d="M16 1v30M1 16h30" stroke="#000" strokeWidth="2" />
      <path d="M8 8l16 16M24 8L8 24" stroke="#000" strokeWidth="2" />
    </svg>
  );
}

function FootballSpinnerIcon({ size = 56 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className="picks-check-spin"
    >
      <circle cx="16" cy="16" r="15" fill="#2d5016" stroke="#000" strokeWidth="1" />
      <ellipse cx="16" cy="16" rx="8" ry="11" fill="#8b4513" stroke="#000" strokeWidth="1.5" />
      <line x1="16" y1="10" x2="16" y2="22" stroke="#fff" strokeWidth="1.5" />
      <line x1="13" y1="13" x2="19" y2="13" stroke="#fff" strokeWidth="1" />
      <line x1="13" y1="16" x2="19" y2="16" stroke="#fff" strokeWidth="1" />
      <line x1="13" y1="19" x2="19" y2="19" stroke="#fff" strokeWidth="1" />
    </svg>
  );
}

/**
 * Sport-aware spinner that renders the correct icon based on sport mode.
 */
export default function SportSpinner({ size = 56 }) {
  const { config } = useSportConfig();
  
  if (config.sport_mode === 'march_madness') {
    return <BasketballSpinnerIcon size={size} />;
  }
  
  return <FootballSpinnerIcon size={size} />;
}
