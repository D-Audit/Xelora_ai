import { cn } from '@/lib/utils';

interface XeloraLogoProps {
  variant?: 'default' | 'dark' | 'light';
  size?: 'sm' | 'md' | 'lg';
  showWordmark?: boolean;
  className?: string;
}

export function XeloraLogo({
  variant = 'default',
  size = 'md',
  showWordmark = true,
  className,
}: XeloraLogoProps) {
  const iconSize = size === 'sm' ? 24 : size === 'md' ? 32 : 40;
  const textSize = size === 'sm' ? 'text-base' : size === 'md' ? 'text-xl' : 'text-2xl';

  const textColour =
    variant === 'light' ? 'text-white' : 'text-xelora-deep-green';

  return (
    <div className={cn('flex items-center gap-2', className)} aria-label="Xelora">
      {/* Abstract X mark from spreadsheet grid cells */}
      <svg
        width={iconSize}
        height={iconSize}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        {/* Grid background cells */}
        <rect x="1" y="1" width="13" height="13" rx="2" fill="#023430" />
        <rect x="18" y="1" width="13" height="13" rx="2" fill="#00684A" />
        <rect x="1" y="18" width="13" height="13" rx="2" fill="#00684A" />
        <rect x="18" y="18" width="13" height="13" rx="2" fill="#023430" />
        {/* X diagonal lines */}
        <line x1="5" y1="5" x2="11" y2="11" stroke="#00ED64" strokeWidth="2.2" strokeLinecap="round" />
        <line x1="11" y1="5" x2="5" y2="11" stroke="#00ED64" strokeWidth="2.2" strokeLinecap="round" />
        <line x1="22" y1="22" x2="28" y2="28" stroke="#00ED64" strokeWidth="2.2" strokeLinecap="round" />
        <line x1="28" y1="22" x2="22" y2="28" stroke="#00ED64" strokeWidth="2.2" strokeLinecap="round" />
        {/* Cross connectors */}
        <line x1="11" y1="11" x2="22" y2="22" stroke="#00ED64" strokeWidth="1.4" strokeLinecap="round" strokeDasharray="2 2" />
        <line x1="22" y1="11" x2="11" y2="22" stroke="#00ED64" strokeWidth="1.4" strokeLinecap="round" strokeDasharray="2 2" />
      </svg>

      {showWordmark && (
        <span className={cn('font-semibold tracking-tight', textSize, textColour)}>
          Xelora
        </span>
      )}
    </div>
  );
}
