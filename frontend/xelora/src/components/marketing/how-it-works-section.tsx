const steps = [
  {
    number: '01',
    title: 'Open your spreadsheet',
    desc: 'Open any .xlsx, .csv, or .ods file directly in Xelora Desktop. Your data stays on your machine unless you choose to sync.',
  },
  {
    number: '02',
    title: 'Describe what you need',
    desc: 'Type what you want to accomplish in plain language. "Remove duplicates and add a revenue total by region" is enough to get started.',
  },
  {
    number: '03',
    title: 'Review the workflow',
    desc: "Xelora AI breaks your request into clear, named steps. Read each one, remove any you don't need, and adjust the order before running.",
  },
  {
    number: '04',
    title: 'Run, edit, and approve',
    desc: 'Steps run one at a time. You can pause, edit the spreadsheet mid-run, approve changes before they apply, and undo anything.',
  },
];

export function HowItWorksSection() {
  return (
    <section className="border-b border-xelora-border bg-xelora-surface-2 py-20" aria-labelledby="how-heading">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mb-14 max-w-2xl">
          <p className="mb-3 text-sm font-medium uppercase tracking-wide text-xelora-green">How it works</p>
          <h2 id="how-heading" className="text-3xl font-semibold leading-tight text-xelora-text">
            From spreadsheet to result in four steps
          </h2>
        </div>

        <div className="relative">
          <div className="absolute bottom-10 left-5 top-10 hidden w-px bg-xelora-border lg:block" aria-hidden="true" />

          <ol className="space-y-8 lg:grid lg:grid-cols-4 lg:gap-8 lg:space-y-0">
            {steps.map((step, index) => (
              <li key={step.number} className="relative flex gap-5 lg:flex-col lg:gap-4">
                <div className="z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 border-xelora-green bg-white text-sm font-semibold text-xelora-green">
                  {index + 1}
                </div>
                <div>
                  <h3 className="mb-2 text-base font-semibold text-xelora-text">{step.title}</h3>
                  <p className="text-sm leading-relaxed text-xelora-text-secondary">{step.desc}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
