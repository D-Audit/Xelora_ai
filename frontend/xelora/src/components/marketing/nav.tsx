'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight, Menu, X } from 'lucide-react';
import { XeloraLogo } from '@/components/ui/xelora-logo';
import { cn } from '@/lib/utils';

const navLinks = [
  ['Product', '/features'], ['Solutions', '/solutions'], ['How it works', '/how-it-works'],
  ['Pricing', '/pricing'], ['Security', '/security'],
];

export function MarketingNav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header className={cn('marketing-nav', scrolled && 'is-scrolled')}>
      <div className="landing-shell nav-inner">
        <Link href="/" aria-label="Xelora home" className="nav-logo"><XeloraLogo variant="light" size="sm" /></Link>
        <nav className="nav-links" aria-label="Main navigation">
          {navLinks.map(([label, href]) => <Link href={href} key={href}>{label}</Link>)}
        </nav>
        <div className="nav-actions"><Link href="/login">Log in</Link><Link href="/register" className="nav-cta">Try Xelora <ArrowUpRight size={15} /></Link></div>
        <button className="nav-toggle" aria-label={open ? 'Close menu' : 'Open menu'} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
      </div>
      <div className={cn('mobile-nav', open && 'is-open')}>
        {navLinks.map(([label, href]) => <Link href={href} key={href} onClick={() => setOpen(false)}>{label}</Link>)}
        <Link href="/register" className="nav-cta" onClick={() => setOpen(false)}>Try Xelora <ArrowUpRight size={15} /></Link>
      </div>
    </header>
  );
}
