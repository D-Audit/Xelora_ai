import type { ReactNode } from 'react';

interface SectionHeadingProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  align?: 'left' | 'center';
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  actions,
  align = 'left',
}: SectionHeadingProps) {
  return (
    <div className={align === 'center' ? 'mx-auto max-w-3xl text-center' : 'max-w-3xl'}>
      {eyebrow ? (
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-xelora-green">
          {eyebrow}
        </p>
      ) : null}
      <div className={actions ? 'mt-2 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between' : 'mt-2'}>
        <div className={align === 'center' ? 'mx-auto max-w-2xl' : ''}>
          <h2 className="text-2xl font-semibold tracking-tight text-xelora-text sm:text-3xl">
            {title}
          </h2>
          {description ? (
            <p className="mt-3 text-sm leading-6 text-xelora-text-secondary sm:text-base">
              {description}
            </p>
          ) : null}
        </div>
        {actions ? <div className={align === 'center' ? 'flex justify-center' : 'shrink-0'}>{actions}</div> : null}
      </div>
    </div>
  );
}
