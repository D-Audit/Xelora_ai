'use client';
import { useState } from 'react';
import { X, Save, Undo2, Redo2, Bold, Italic, AlignLeft, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface Props { fileName: string; onClose: () => void; }

const COLS = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
const ROWS = 12;

const MOCK_DATA: Record<string, string> = {
  'A1': 'Date', 'B1': 'Region', 'C1': 'Product', 'D1': 'Units', 'E1': 'Unit Price', 'F1': 'Revenue', 'G1': 'District',
  'A2': '2026-07-01', 'B2': 'North', 'C2': 'Widget A', 'D2': '142', 'E2': '24.99', 'F2': '=D2*E2', 'G2': 'Manchester',
  'A3': '2026-07-01', 'B3': 'South', 'C3': 'Widget B', 'D3': '88', 'E3': '34.50', 'F3': '=D3*E3', 'G3': 'london',
  'A4': '2026-07-02', 'B4': 'East', 'C4': 'Widget A', 'D4': '203', 'E4': '24.99', 'F4': '=D4*E4', 'G4': 'Birmingham',
  'A5': '2026-07-02', 'B5': 'North', 'C5': 'Widget C', 'D5': '67', 'E5': '19.00', 'F5': '=D5*E5', 'G5': 'Manchester',
  'A6': '2026-07-03', 'B6': 'West', 'C6': 'Widget B', 'D6': '115', 'E6': '34.50', 'F6': '=D6*E6', 'G6': 'BRISTOL',
  'A7': '2026-07-03', 'B7': 'South', 'C7': 'Widget A', 'D7': '77', 'E7': '24.99', 'F7': '=D7*E7', 'G7': 'London',
};

const SHEETS = ['Sales', 'Returns', 'Targets'];

export function SpreadsheetWorkspace({ fileName, onClose }: Props) {
  const [activeSheet, setActiveSheet] = useState('Sales');
  const [selectedCell, setSelectedCell] = useState<string | null>('A1');
  const [formulaBar, setFormulaBar] = useState('');

  const cellKey = (col: string, row: number) => `${col}${row}`;
  const isHeader = (row: number) => row === 1;

  const selectCell = (key: string) => {
    setSelectedCell(key);
    setFormulaBar(MOCK_DATA[key] ?? '');
  };

  return (
    <div className="flex h-full flex-col bg-white overflow-hidden">
      {/* Compact toolbar */}
      <div className="flex items-center gap-1 border-b border-xelora-border px-3 py-1.5 bg-xelora-surface-2 shrink-0 flex-wrap">
        <button onClick={() => toast.success('File saved.')} className="toolbar-btn" title="Save"><Save className="h-3.5 w-3.5" /></button>
        <div className="h-4 w-px bg-xelora-border mx-1" />
        <button onClick={() => toast.info('Undo')} className="toolbar-btn" title="Undo"><Undo2 className="h-3.5 w-3.5" /></button>
        <button onClick={() => toast.info('Redo')} className="toolbar-btn" title="Redo"><Redo2 className="h-3.5 w-3.5" /></button>
        <div className="h-4 w-px bg-xelora-border mx-1" />
        <button onClick={() => toast.info('Bold')} className="toolbar-btn" title="Bold"><Bold className="h-3.5 w-3.5" /></button>
        <button onClick={() => toast.info('Italic')} className="toolbar-btn" title="Italic"><Italic className="h-3.5 w-3.5" /></button>
        <button onClick={() => toast.info('Align')} className="toolbar-btn" title="Align"><AlignLeft className="h-3.5 w-3.5" /></button>
        <div className="h-4 w-px bg-xelora-border mx-1" />
        <button
          onClick={() => toast.info('Ask Xelora: type your question in the task thread.')}
          className="flex items-center gap-1 rounded-md border border-xelora-border bg-white px-2 py-1 text-xs text-xelora-green hover:bg-xelora-success-bg transition-colors"
          title="Ask Xelora"
        >
          <Sparkles className="h-3.5 w-3.5" />Ask Xelora
        </button>
        <div className="flex-1" />
        <span className="text-xs text-xelora-text-muted">{fileName}</span>
        <button onClick={onClose} className="toolbar-btn ml-1" title="Close spreadsheet view">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Formula bar */}
      <div className="flex items-center gap-2 border-b border-xelora-border px-3 py-1.5 shrink-0">
        <span className="w-10 text-center rounded border border-xelora-border bg-xelora-surface-2 px-2 py-0.5 text-xs font-mono text-xelora-text-secondary shrink-0">
          {selectedCell ?? ''}
        </span>
        <div className="h-4 w-px bg-xelora-border" />
        <input
          type="text"
          value={formulaBar}
          onChange={e => setFormulaBar(e.target.value)}
          className="flex-1 text-sm font-mono text-xelora-text focus:outline-none"
          aria-label="Formula bar"
        />
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-auto">
        <table className="text-xs border-collapse min-w-full">
          <thead className="sticky top-0 z-10">
            <tr>
              <th className="w-8 border border-xelora-border bg-xelora-surface-2 px-2 py-1 text-center text-xelora-text-muted" />
              {COLS.map(col => (
                <th key={col} className="border border-xelora-border bg-xelora-surface-2 px-8 py-1 text-center font-medium text-xelora-text-secondary min-w-[100px]">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: ROWS }, (_, i) => i + 1).map(row => (
              <tr key={row}>
                <td className="border border-xelora-border bg-xelora-surface-2 px-2 py-1 text-center text-xelora-text-muted font-medium w-8 shrink-0">
                  {row}
                </td>
                {COLS.map(col => {
                  const key = cellKey(col, row);
                  const val = MOCK_DATA[key] ?? '';
                  const isSelected = selectedCell === key;
                  const warn = row > 1 && col === 'G' && val && val !== val.charAt(0).toUpperCase() + val.slice(1).toLowerCase() && val !== val.toUpperCase();
                  return (
                    <td
                      key={key}
                      onClick={() => selectCell(key)}
                      className={cn(
                        'border border-xelora-border px-2 py-1 cursor-cell min-w-[100px] transition-colors',
                        isSelected ? 'bg-xelora-info-bg outline outline-1 outline-xelora-info' : isHeader(row) ? 'bg-xelora-surface-2 font-semibold' : 'bg-white hover:bg-xelora-surface-2',
                        warn && 'bg-xelora-warning-bg'
                      )}
                    >
                      <span className={cn('block truncate max-w-[120px]', isHeader(row) ? 'text-xelora-text' : 'text-xelora-text-secondary')}>
                        {val}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Sheet tabs */}
      <div className="flex items-center gap-0.5 border-t border-xelora-border px-3 py-1 bg-xelora-surface-2 shrink-0 overflow-x-auto">
        {SHEETS.map(sheet => (
          <button
            key={sheet}
            onClick={() => setActiveSheet(sheet)}
            className={cn(
              'rounded-t-md px-4 py-1 text-xs transition-colors border border-b-0',
              activeSheet === sheet
                ? 'bg-white border-xelora-border text-xelora-text font-medium'
                : 'border-transparent text-xelora-text-secondary hover:bg-xelora-border'
            )}
          >
            {sheet}
          </button>
        ))}
      </div>

      <style jsx>{`
        .toolbar-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 28px;
          width: 28px;
          border-radius: 4px;
          color: #5C6C75;
          transition: background 0.15s;
        }
        .toolbar-btn:hover { background: #DDE5E2; }
      `}</style>
    </div>
  );
}
