export function TrustSection() {
  const categories = [
    'Finance teams',
    'Operations teams',
    'Accountants',
    'Analysts',
    'Small businesses',
    'Researchers',
  ];

  return (
    <section className="bg-xelora-surface-2 border-b border-xelora-border py-10">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <p className="text-center text-sm font-medium text-xelora-text-secondary mb-8">
          Built for people who work with spreadsheets every day
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          {categories.map((cat) => (
            <span
              key={cat}
              className="rounded-full border border-xelora-border bg-white px-4 py-2 text-sm font-medium text-xelora-text"
            >
              {cat}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
