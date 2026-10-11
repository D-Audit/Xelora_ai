import type { Device } from '@/types';

export const mockDevices: Device[] = [
  {
    id: 'device-1',
    userId: 'user-1',
    name: 'Work Laptop',
    os: 'windows',
    appVersion: '1.3.0',
    lastActiveAt: '2026-07-24T08:30:00Z',
    region: 'London, UK',
    status: 'active',
    isPrimary: true,
    authorisedAt: '2025-09-15T10:00:00Z',
  },
  {
    id: 'device-2',
    userId: 'user-1',
    name: 'Home Desktop',
    os: 'windows',
    appVersion: '1.2.4',
    lastActiveAt: '2026-07-18T20:00:00Z',
    region: 'London, UK',
    status: 'inactive',
    isPrimary: false,
    authorisedAt: '2025-10-02T14:00:00Z',
  },
];
