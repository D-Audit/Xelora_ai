import Link from 'next/link';
import { ArrowRight, Check, FileSpreadsheet, LockKeyhole, Play, Sparkles, WandSparkles, Workflow } from 'lucide-react';
import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';

const workflowSteps = [
  ['01', 'Understand', 'Xelora reads the workbook structure, formulas, and context before touching a cell.'],
  ['02', 'Propose', 'You get a plain-language plan with the sheets, ranges, and expected changes.'],
  ['03', 'Execute', 'Approve once, then watch every verified action happen live inside Excel.'],
];

export default function HomePage() {
  return (
    <div className="xelora-landing">
      <MarketingNav />
      <main>
        <section className="hero-stage" aria-labelledby="hero-title">
          <div className="hero-orb hero-orb-one" /><div className="hero-orb hero-orb-two" /><div className="hero-grid" />
          <div className="landing-shell hero-layout">
            <div className="hero-copy reveal-up">
              <div className="eyebrow-pill"><Sparkles size={14} /> AI that works inside Excel</div>
              <h1 id="hero-title">Give busywork to AI.<br />Keep the <em>final say.</em></h1>
              <p className="hero-lede">Turn plain-English requests into accurate, reviewable Excel workflows—without migrating your files or surrendering control.</p>
              <div className="hero-actions">
                <Link href="/register" className="button-primary">Start building free <ArrowRight size={17} /></Link>
                <Link href="/how-it-works" className="button-quiet"><span className="play-dot"><Play size={13} fill="currentColor" /></span> See it in action</Link>
              </div>
              <div className="hero-proof"><span><Check size={14} /> No credit card</span><span><Check size={14} /> Native .xlsx files</span><span><Check size={14} /> Approval before edits</span></div>
            </div>

            <div className="product-scene reveal-up delay-one" aria-label="Animated preview of Xelora automating an Excel workbook">
              <div className="scene-glow" />
              <div className="excel-window">
                <div className="window-bar"><div className="traffic"><i /><i /><i /></div><span>Q3 Revenue.xlsx</span><small>Saved</small></div>
                <div className="excel-ribbon"><strong>File</strong><span>Home</span><span>Insert</span><span>Formulas</span><span>Data</span></div>
                <div className="sheet-area"><div className="sheet-grid">
                  <div className="sheet-head"><b>REGION</b><b>REVENUE</b><b>GROWTH</b></div>
                  {[["North", "$128,400", "+18.2%"], ["South", "$96,820", "+12.4%"], ["East", "$141,250", "+21.7%"], ["West", "$110,090", "+15.1%"]].map((row, index) => <div className={`sheet-row row-${index}`} key={row[0]}><span>{row[0]}</span><span>{row[1]}</span><span>{row[2]}</span></div>)}
                  <div className="chart-card"><div><span>Revenue by region</span><strong>$476.5k</strong></div><div className="bars"><i /><i /><i /><i /></div></div>
                </div></div>
                <div className="sheet-tabs"><b>Summary</b><span>Raw data</span><span>Forecast</span></div>
              </div>
              <div className="agent-card">
                <div className="agent-top"><span className="agent-mark"><WandSparkles size={15} /></span><b>Xelora</b><small>Working live</small></div>
                <p>Build a regional revenue summary and highlight the strongest growth.</p>
                <div className="task-progress"><i /></div>
                <ul><li className="done"><Check size={13} /> Analysed 4,218 rows</li><li className="done"><Check size={13} /> Created Summary sheet</li><li className="active"><span /> Formatting chart</li></ul>
                <div className="approval"><LockKeyhole size={14} /><span><b>Approval protected</b><small>No change happens unseen</small></span></div>
              </div>
              <div className="floating-badge"><span>69</span> native Excel skills</div>
            </div>
          </div>
          <div className="landing-shell trust-line"><span>BUILT FOR THE WORK THAT LIVES IN</span><strong>Excel</strong><i />Finance<i />Operations<i />Reporting<i />Analytics</div>
        </section>

        <section className="landing-section problem-section">
          <div className="landing-shell split-heading"><div><span className="section-kicker">Your workbook. Upgraded.</span><h2>From messy request to<br /><em>finished workbook.</em></h2></div><p>Xelora handles the repetitive mechanics while preserving the formulas, formatting, and familiar Excel surface your team already trusts.</p></div>
          <div className="landing-shell bento-grid">
            <article className="bento-card bento-wide lime-card"><span className="card-number">01 / NATURAL LANGUAGE</span><h3>Ask for the outcome,<br />not the formula.</h3><div className="prompt-demo"><span>✦</span><p>“Clean the sales data, remove duplicates, and build a regional summary.”</p><button aria-label="Submit example prompt"><ArrowRight size={18} /></button></div></article>
            <article className="bento-card dark-card"><div className="card-icon"><LockKeyhole size={20} /></div><h3>Nothing changes until you approve it.</h3><p>See the plan, affected ranges, and expected result before execution begins.</p><div className="mini-approval"><Check size={13} /> Plan approved by you</div></article>
            <article className="bento-card cream-card"><div className="card-icon"><Workflow size={20} /></div><h3>Make great work repeatable.</h3><p>Save any multi-step process as a reusable workflow for next week, next month, or your whole team.</p><div className="workflow-mini"><i /><i /><i /><i /></div></article>
            <article className="bento-card bento-wide visual-card"><div><span className="card-number">69 TESTED SKILLS</span><h3>Deep Excel capability.<br />One calm interface.</h3></div><div className="skill-cloud">{['Pivots', 'Power Query', 'Charts', 'VBA', 'Formulas', 'Cleanup', 'Imports', 'Validation'].map((skill) => <span key={skill}>{skill}</span>)}</div></article>
          </div>
        </section>

        <section className="landing-section workflow-section" id="how-it-works">
          <div className="landing-shell workflow-intro"><span className="section-kicker light">Designed around trust</span><h2>A smarter workflow,<br /><em>with you in the loop.</em></h2></div>
          <div className="landing-shell workflow-list">{workflowSteps.map(([number, title, copy]) => <article key={number}><span>{number}</span><h3>{title}</h3><p>{copy}</p><ArrowRight size={19} /></article>)}</div>
        </section>

        <section className="landing-section final-cta"><div className="cta-orbit" /><div className="landing-shell cta-inner"><div className="cta-icon"><FileSpreadsheet size={27} /></div><span className="section-kicker">Your next workbook can be easier</span><h2>Less spreadsheet work.<br /><em>More actual progress.</em></h2><p>Bring the workbook. Describe the outcome. Xelora handles the rest—with your approval at every important step.</p><Link href="/register" className="button-primary dark-button">Start your free trial <ArrowRight size={17} /></Link></div></section>
      </main>
      <MarketingFooter />
    </div>
  );
}
