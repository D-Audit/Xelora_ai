'use client';

import { useEffect, useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getInvoices } from '@/services/billing';
import type { InvoiceSummary } from '@/services/billing';
import { formatCurrency, formatDate } from '@/lib/utils';

export default function BillingInvoicesPage() {
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    getInvoices()
      .then((res) => setInvoices(res.invoices))
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Could not load invoices.'))
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Billing"
        title="Invoices"
        description="Review your invoice history, generated from real Stripe payments once billing is live."
      />
      <Card className="overflow-hidden">
        {isLoading ? (
          <div className="flex h-40 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-xelora-text-muted" />
          </div>
        ) : invoices.length === 0 ? (
          <div className="p-8 text-center text-sm text-xelora-text-secondary">
            No invoices yet. They&apos;ll appear here once a paid plan renews.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-xelora-surface-2">
                <tr className="border-b border-xelora-border text-left">
                  <th className="px-5 py-3 text-xelora-text-secondary">Description</th>
                  <th className="px-4 py-3 text-xelora-text-secondary">Issued</th>
                  <th className="px-4 py-3 text-xelora-text-secondary">Period</th>
                  <th className="px-4 py-3 text-xelora-text-secondary">Amount</th>
                  <th className="px-4 py-3 text-xelora-text-secondary">Status</th>
                  <th className="px-4 py-3 text-right text-xelora-text-secondary">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-xelora-border bg-white">
                {invoices.map((invoice) => (
                  <tr key={invoice.id}>
                    <td className="px-5 py-3 text-xelora-text">{invoice.description ?? 'Subscription'}</td>
                    <td className="px-4 py-3 text-xelora-text-secondary">{invoice.issuedAt ? formatDate(invoice.issuedAt) : '—'}</td>
                    <td className="px-4 py-3 text-xelora-text-secondary">
                      {invoice.periodStart && invoice.periodEnd ? `${formatDate(invoice.periodStart)} - ${formatDate(invoice.periodEnd)}` : '—'}
                    </td>
                    <td className="px-4 py-3 text-xelora-text-secondary">{formatCurrency(invoice.amount)}</td>
                    <td className="px-4 py-3">
                      <Badge variant={invoice.status === 'paid' ? 'success' : 'warning'}>{invoice.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button variant="ghost" size="sm" onClick={() => toast.info('Invoice PDF download requires a Stripe customer portal - see INTEGRATION.md.')}>
                        <Download className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
