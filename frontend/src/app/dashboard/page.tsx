import { redirect } from 'next/navigation';

/** Chat is the home of the app. */
export default function DashboardHome() {
  redirect('/dashboard/agent');
}
