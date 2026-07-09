import { app } from 'electron';
import fs from 'node:fs/promises';
import path from 'node:path';
import type {
  DesktopSettings,
  RecentFile,
  SessionState,
} from '../../shared/types';
import { defaultDesktopSettings } from '../../shared/types';

type StoredState = {
  settings: DesktopSettings;
  recentFiles: RecentFile[];
  session: SessionState | null;
  windowBounds: { x: number; y: number; width: number; height: number } | null;
  isDirty: boolean;
};

const defaultState: StoredState = {
  settings: defaultDesktopSettings,
  recentFiles: [],
  session: null,
  windowBounds: null,
  isDirty: false,
};

export class JsonStore {
  private readonly filePath: string;
  private state: StoredState = defaultState;
  private initialized = false;

  constructor(filename: string) {
    this.filePath = path.join(app.getPath('userData'), filename);
  }

  async init(): Promise<void> {
    if (this.initialized) {
      return;
    }

    try {
      const raw = await fs.readFile(this.filePath, 'utf-8');
      const parsed = JSON.parse(raw) as Partial<StoredState>;
      this.state = {
        ...defaultState,
        ...parsed,
        settings: {
          ...defaultDesktopSettings,
          ...parsed.settings,
          general: { ...defaultDesktopSettings.general, ...parsed.settings?.general },
          files: { ...defaultDesktopSettings.files, ...parsed.settings?.files },
          ai: { ...defaultDesktopSettings.ai, ...parsed.settings?.ai },
          privacy: { ...defaultDesktopSettings.privacy, ...parsed.settings?.privacy },
          application: { ...defaultDesktopSettings.application, ...parsed.settings?.application },
        },
      };
    } catch {
      this.state = defaultState;
    }

    this.initialized = true;
    await this.persist();
  }

  getState(): StoredState {
    return this.state;
  }

  async update(
    patch: Partial<Omit<StoredState, 'settings'>> & {
      settings?: Partial<DesktopSettings>;
    },
  ): Promise<void> {
    this.state = {
      ...this.state,
      ...patch,
      settings: patch.settings
        ? {
            ...defaultDesktopSettings,
            ...patch.settings,
            general: { ...this.state.settings.general, ...patch.settings.general },
            files: { ...this.state.settings.files, ...patch.settings.files },
            ai: { ...this.state.settings.ai, ...patch.settings.ai },
            privacy: { ...this.state.settings.privacy, ...patch.settings.privacy },
            application: { ...this.state.settings.application, ...patch.settings.application },
          }
        : this.state.settings,
    };
    await this.persist();
  }

  async persist(): Promise<void> {
    await fs.mkdir(path.dirname(this.filePath), { recursive: true });
    await fs.writeFile(this.filePath, JSON.stringify(this.state, null, 2), 'utf-8');
  }

  setWindowBounds(bounds: NonNullable<StoredState['windowBounds']>): Promise<void> {
    return this.update({ windowBounds: bounds });
  }

  setDirty(isDirty: boolean): Promise<void> {
    return this.update({ isDirty });
  }
}

export function createUserDataPath(...segments: string[]): string {
  return path.join(app.getPath('userData'), ...segments);
}
