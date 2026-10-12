import { Fragment } from 'react';

/**
 * A small, safe Markdown renderer for chat replies: paragraphs, headings,
 * lists, bold, italic, inline code, code blocks, links and [n] citations.
 * It builds React elements (never raw HTML), and only http(s) links render.
 */
interface Source { n: number; url: string; title: string }

const INLINE = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*\s][^*]*\*|\[[^\]]+\]\((https?:\/\/[^)\s]+)\)|\[\d{1,2}\])/g;

function inline(text: string, sources: Source[], keyPrefix: string) {
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(INLINE)) {
    const token = match[0];
    const index = match.index ?? 0;
    if (index > last) parts.push(text.slice(last, index));
    const key = `${keyPrefix}-${index}`;
    if (token.startsWith('`')) {
      parts.push(<code key={key} className="rounded bg-xelora-surface-2 px-1 py-0.5 font-mono text-[0.85em] text-xelora-text">{token.slice(1, -1)}</code>);
    } else if (token.startsWith('**')) {
      parts.push(<strong key={key} className="font-semibold text-xelora-text">{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('*')) {
      parts.push(<em key={key}>{token.slice(1, -1)}</em>);
    } else if (/^\[\d{1,2}\]$/.test(token)) {
      const source = sources.find((item) => item.n === Number(token.slice(1, -1)));
      parts.push(source ? (
        <a key={key} href={source.url} target="_blank" rel="noopener noreferrer nofollow" title={source.title}
          className="mx-0.5 inline-flex h-4 min-w-4 -translate-y-0.5 items-center justify-center rounded bg-xelora-surface-2 px-1 align-middle text-[10px] font-medium text-xelora-text-secondary no-underline hover:bg-xelora-border">
          {source.n}
        </a>
      ) : token);
    } else {
      const label = token.slice(1, token.indexOf(']('));
      parts.push(
        <a key={key} href={match[2]} target="_blank" rel="noopener noreferrer nofollow" className="text-xelora-green underline underline-offset-2">
          {label}
        </a>,
      );
    }
    last = index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

type Block =
  | { type: 'p'; text: string }
  | { type: 'h'; text: string; level: number }
  | { type: 'ul'; items: string[] }
  | { type: 'ol'; items: string[] }
  | { type: 'code'; text: string };

function parse(markdown: string): Block[] {
  const blocks: Block[] = [];
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim().startsWith('```')) {
      const code: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith('```')) code.push(lines[i++]);
      i += 1;
      blocks.push({ type: 'code', text: code.join('\n') });
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      blocks.push({ type: 'h', level: heading[1].length, text: heading[2] });
      i += 1;
      continue;
    }
    if (/^\s*[-*•]\s+/.test(line) || /^\s*\d+[.)]\s+/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line);
      const items: string[] = [];
      while (i < lines.length && (ordered ? /^\s*\d+[.)]\s+/ : /^\s*[-*•]\s+/).test(lines[i])) {
        items.push(lines[i].replace(ordered ? /^\s*\d+[.)]\s+/ : /^\s*[-*•]\s+/, ''));
        i += 1;
      }
      blocks.push({ type: ordered ? 'ol' : 'ul', items });
      continue;
    }
    if (!line.trim()) {
      i += 1;
      continue;
    }
    const paragraph: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|```|\s*[-*•]\s+|\s*\d+[.)]\s+)/.test(lines[i])) {
      paragraph.push(lines[i++]);
    }
    blocks.push({ type: 'p', text: paragraph.join('\n') });
  }
  return blocks;
}

export function Markdown({ text, sources = [] }: { text: string; sources?: Source[] }) {
  return (
    <div className="space-y-3 text-[15px] leading-7 text-xelora-text">
      {parse(text).map((block, index) => {
        const key = `b${index}`;
        if (block.type === 'code') {
          return <pre key={key} className="overflow-x-auto rounded-lg bg-xelora-surface-2 p-3 font-mono text-[13px] leading-6">{block.text}</pre>;
        }
        if (block.type === 'h') {
          return <p key={key} className="pt-1 font-semibold text-xelora-text">{inline(block.text, sources, key)}</p>;
        }
        if (block.type === 'ul' || block.type === 'ol') {
          const List = block.type;
          return (
            <List key={key} className={`space-y-1 pl-5 ${block.type === 'ul' ? 'list-disc' : 'list-decimal'} marker:text-xelora-text-muted`}>
              {block.items.map((item, itemIndex) => <li key={itemIndex} className="pl-1">{inline(item, sources, `${key}-${itemIndex}`)}</li>)}
            </List>
          );
        }
        return (
          <p key={key} className="break-words">
            {block.text.split('\n').map((line, lineIndex) => (
              <Fragment key={lineIndex}>{lineIndex > 0 && <br />}{inline(line, sources, `${key}-${lineIndex}`)}</Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
