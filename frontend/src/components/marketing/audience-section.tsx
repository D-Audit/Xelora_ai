const audiences = [
  {
    title: 'Accountants',
    description: 'Automate reconciliations, VAT returns, payroll validation, and monthly close processes. Stop repeating the same steps every period.',
    useCases: ['Monthly reconciliation', 'Payroll data cleaning', 'VAT summary reports'],
  },
  {
    title: 'Small businesses',
    description: 'Handle invoicing data, stock reports, and expense tracking without a dedicated data team. Simple enough to use without training.',
    useCases: ['Invoice processing', 'Stock level monitoring', 'Expense categorisation'],
  },
  {
    title: 'Human resources',
    description: 'Process headcount reports, validate onboarding data, and clean HR system exports before they go into payroll.',
    useCases: ['Onboarding data validation', 'Headcount reporting', 'Payroll preparation'],
  },
  {
    title: 'Data analysts',
    description: 'Speed up the tedious parts of data work — cleaning, deduplication, and formatting — so you can focus on the analysis itself.',
    useCases: ['Data normalisation', 'Deduplication', 'Format standardisation'],
  },
  {
    title: 'Students and researchers',
    description: 'Clean survey responses, calculate statistics, and prepare data for reports without spending hours on formatting.',
    useCases: ['Survey data cleaning', 'Grade book analysis', 'Research data prep'],
  },
  {
    title: 'Operations teams',
    description: 'Process supplier data, manage inventory spreadsheets, and generate operational reports on a regular schedule.',
    useCases: ['Inventory reorder reports', 'Supplier data matching', 'KPI dashboards'],
  },
];

export function AudienceSection() {
  return (
    <section className="py-20 bg-white border-b border-xelora-border" aria-labelledby="audience-heading">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl mb-14">
          <p className="text-sm font-medium text-xelora-green uppercase tracking-wide mb-3">Who uses Xelora</p>
          <h2 id="audience-heading" className="text-3xl font-semibold text-xelora-text leading-tight">
            Built for the work you actually do
          </h2>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {audiences.map(({ title, description, useCases }) => (
            <div key={title} className="rounded-lg border border-xelora-border bg-white p-6">
              <h3 className="text-base font-semibold text-xelora-text mb-2">{title}</h3>
              <p className="text-sm text-xelora-text-secondary leading-relaxed mb-4">{description}</p>
              <ul className="space-y-1.5">
                {useCases.map(uc => (
                  <li key={uc} className="flex items-center gap-2 text-xs text-xelora-text-secondary">
                    <span className="h-1.5 w-1.5 rounded-full bg-xelora-green shrink-0" aria-hidden="true" />
                    {uc}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
