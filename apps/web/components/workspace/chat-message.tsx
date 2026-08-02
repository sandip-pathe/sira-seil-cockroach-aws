import type { ReactNode } from "react";

import styles from "./commerce-workspace.module.css";

type ChatMessageBodyProps = {
  content: string;
  tone?: "assistant" | "user";
};

const BLOCK_START = /^(#{1,4}\s|[-*+]\s+|\d+\.\s+|>\s?|```)/;
const SAFE_LINK = /^(https?:\/\/|mailto:|\/|#)/i;

function parseInline(text: string, keyPrefix: string): ReactNode[] {
  const tokenPattern =
    /(`[^`]+`|\*\*[^*\n][\s\S]*?[^*\n]\*\*|\*[^*\n][^*\n]*\*|\[[^\]\n]+\]\([^) \n]+\))/g;
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenPattern.exec(text))) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));

    const token = match[0];
    const key = `${keyPrefix}-${match.index}`;

    if (token.startsWith("`") && token.endsWith("`")) {
      nodes.push(<code key={key}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith("**") && token.endsWith("**")) {
      nodes.push(
        <strong key={key}>
          {parseInline(token.slice(2, -2), `${key}-strong`)}
        </strong>,
      );
    } else if (token.startsWith("*") && token.endsWith("*")) {
      nodes.push(
        <em key={key}>{parseInline(token.slice(1, -1), `${key}-em`)}</em>,
      );
    } else {
      const link = token.match(/^\[([^\]\n]+)\]\(([^) \n]+)\)$/);
      if (link && SAFE_LINK.test(link[2])) {
        nodes.push(
          <a
            key={key}
            href={link[2]}
            rel={link[2].startsWith("http") ? "noreferrer" : undefined}
            target={link[2].startsWith("http") ? "_blank" : undefined}
          >
            {parseInline(link[1], `${key}-link`)}
          </a>,
        );
      } else {
        nodes.push(token);
      }
    }

    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

function collectParagraph(lines: string[], startIndex: number) {
  const paragraph: string[] = [];
  let index = startIndex;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim() || BLOCK_START.test(line.trim())) break;
    paragraph.push(line.trim());
    index += 1;
  }

  return { nextIndex: index, text: paragraph.join(" ") };
}

function renderBlocks(content: string) {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();

    if (!line) {
      index += 1;
      continue;
    }

    if (line.startsWith("```")) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push(
        <pre key={`code-${index}`}>
          <code>{codeLines.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      const level = Math.min(heading[1].length, 4);
      const Heading = `h${level}` as "h1" | "h2" | "h3" | "h4";
      blocks.push(
        <Heading key={`heading-${index}`}>
          {parseInline(heading[2], `heading-${index}`)}
        </Heading>,
      );
      index += 1;
      continue;
    }

    const unordered = /^[-*+]\s+(.+)$/.test(line);
    const ordered = /^\d+\.\s+(.+)$/.test(line);
    if (unordered || ordered) {
      const items: string[] = [];
      const marker = ordered ? /^\d+\.\s+(.+)$/ : /^[-*+]\s+(.+)$/;
      while (index < lines.length) {
        const item = lines[index].trim().match(marker);
        if (!item) break;
        items.push(item[1]);
        index += 1;
      }
      const List = ordered ? "ol" : "ul";
      blocks.push(
        <List key={`list-${index}`}>
          {items.map((item, itemIndex) => (
            <li key={`${index}-${itemIndex}`}>
              {parseInline(item, `list-${index}-${itemIndex}`)}
            </li>
          ))}
        </List>,
      );
      continue;
    }

    const paragraph = collectParagraph(lines, index);
    blocks.push(
      <p key={`paragraph-${index}`}>
        {parseInline(paragraph.text, `paragraph-${index}`)}
      </p>,
    );
    index = paragraph.nextIndex;
  }

  return blocks;
}

export function ChatMessageBody({
  content,
  tone = "assistant",
}: ChatMessageBodyProps) {
  return (
    <div
      className={styles.messageBody}
      data-tone={tone}
      data-pretext-message
    >
      {content.trim() ? renderBlocks(content) : null}
    </div>
  );
}
