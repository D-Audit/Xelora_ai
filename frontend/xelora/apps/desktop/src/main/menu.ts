import { Menu, type MenuItemConstructorOptions, shell } from 'electron';
import type { BrowserWindow } from 'electron';

export type MenuAction =
  | 'new-workbook'
  | 'open-workbook'
  | 'open-csv'
  | 'save-workbook'
  | 'save-workbook-as'
  | 'export-copy'
  | 'undo'
  | 'redo'
  | 'find'
  | 'replace'
  | 'run-workflow'
  | 'pause-workflow'
  | 'toggle-workflow-panel'
  | 'toggle-ai-panel'
  | 'clean-data'
  | 'about'
  | 'docs';

export function createAppMenu(windowRef: BrowserWindow): void {
  const template: MenuItemConstructorOptions[] = [
    {
      label: 'File',
      submenu: [
        { label: 'New Workbook', accelerator: 'Ctrl+N', click: () => windowRef.webContents.send('menu-action', 'new-workbook') },
        { label: 'Open', accelerator: 'Ctrl+O', click: () => windowRef.webContents.send('menu-action', 'open-workbook') },
        { label: 'Open Recent', enabled: false },
        { type: 'separator' },
        { label: 'Save', accelerator: 'Ctrl+S', click: () => windowRef.webContents.send('menu-action', 'save-workbook') },
        { label: 'Save As', accelerator: 'Ctrl+Shift+S', click: () => windowRef.webContents.send('menu-action', 'save-workbook-as') },
        { label: 'Export Copy', click: () => windowRef.webContents.send('menu-action', 'export-copy') },
        { type: 'separator' },
        { role: 'close' },
        { role: 'quit' },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { label: 'Undo', accelerator: 'Ctrl+Z', click: () => windowRef.webContents.send('menu-action', 'undo') },
        { label: 'Redo', accelerator: 'Ctrl+Y', click: () => windowRef.webContents.send('menu-action', 'redo') },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { type: 'separator' },
        { label: 'Find', accelerator: 'Ctrl+F', click: () => windowRef.webContents.send('menu-action', 'find') },
        { label: 'Replace', accelerator: 'Ctrl+H', click: () => windowRef.webContents.send('menu-action', 'replace') },
      ],
    },
    {
      label: 'Data',
      submenu: [
        { label: 'Sort', enabled: false },
        { label: 'Filter', enabled: false },
        { label: 'Clean Data', click: () => windowRef.webContents.send('menu-action', 'clean-data') },
        { label: 'Remove Duplicates', enabled: false },
        { label: 'Validate Data', enabled: false },
      ],
    },
    {
      label: 'Automation',
      submenu: [
        { label: 'Ask Xelora AI', accelerator: 'Ctrl+K', click: () => windowRef.webContents.send('menu-action', 'toggle-ai-panel') },
        { label: 'Review Workflow', click: () => windowRef.webContents.send('menu-action', 'toggle-workflow-panel') },
        { label: 'Run Workflow', accelerator: 'Ctrl+Enter', click: () => windowRef.webContents.send('menu-action', 'run-workflow') },
        { label: 'Pause Workflow', click: () => windowRef.webContents.send('menu-action', 'pause-workflow') },
        { label: 'Workflow History', enabled: false },
      ],
    },
    {
      label: 'View',
      submenu: [
        { label: 'Toggle Workflow Panel', click: () => windowRef.webContents.send('menu-action', 'toggle-workflow-panel') },
        { label: 'Toggle AI Panel', click: () => windowRef.webContents.send('menu-action', 'toggle-ai-panel') },
        { type: 'separator' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { role: 'resetZoom' },
        { type: 'separator' },
        { role: 'togglefullscreen', accelerator: 'F11' },
      ],
    },
    {
      label: 'Help',
      submenu: [
        { label: 'Documentation', click: () => shell.openExternal('https://xelora.app/docs') },
        { label: 'About Xelora', click: () => windowRef.webContents.send('menu-action', 'about') },
      ],
    },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}
