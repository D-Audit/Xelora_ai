import Link from 'next/link';
import { Check, Sparkles } from 'lucide-react';
import { XeloraLogo } from '@/components/ui/xelora-logo';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="auth-shell">
      <div className="auth-ambient auth-ambient-one" />
      <div className="auth-ambient auth-ambient-two" />
      <section className="auth-frame">
        <aside className="auth-visual" aria-label="Xelora product overview">
          <div className="auth-visual-grid" />
          <div className="auth-visual-glow" />
          <Link href="/" className="auth-brand" aria-label="Xelora home">
            <XeloraLogo variant="light" size="md" />
          </Link>

          <div className="auth-story">
            <span className="auth-kicker"><Sparkles size={13} /> Excel work, beautifully automated</span>
            <h2>Turn intent into<br /><em>finished work.</em></h2>
            <p>Describe the outcome. Review the plan. Watch Xelora complete the spreadsheet work while you stay in control.</p>
          </div>

          <div className="auth-workbook" aria-hidden="true">
            <div className="auth-workbook-bar"><i /><i /><i /><span>Revenue forecast.xlsx</span></div>
            <div className="auth-workbook-body">
              <div className="auth-sheet-labels"><b>A</b><b>B</b><b>C</b><b>D</b><b>E</b></div>
              <div className="auth-sheet-cells">
                {Array.from({ length: 20 }).map((_, index) => <i key={index} className={index === 6 || index === 12 || index === 13 ? 'active' : ''} />)}
              </div>
              <div className="auth-chart"><i /><i /><i /><i /></div>
            </div>
          </div>

          <div className="auth-status-card">
            <span><Check size={13} /></span>
            <div><b>Plan verified</b><small>8 actions ready for approval</small></div>
          </div>
          <p className="auth-testimonial">“What took an afternoon now takes one reviewed workflow.”</p>
        </aside>

        <div className="auth-form-side">
          <div className="auth-mobile-brand"><Link href="/"><XeloraLogo size="md" /></Link></div>
          <div className="auth-form-scroll">{children}</div>
          <p className="auth-legal-note">Protected by enterprise-grade encryption · Your workbook stays yours</p>
        </div>
      </section>
    </main>
  );
}
