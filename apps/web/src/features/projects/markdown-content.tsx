type MarkdownBlock =
  | { type: "heading"; level: number; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; ordered: boolean; items: string[] };

type MarkdownContentProps = {
  markdown: string;
  className?: string;
};

export function MarkdownContent({
  markdown,
  className = "mt-5 space-y-5 text-sm leading-7 text-muted-foreground",
}: MarkdownContentProps) {
  const blocks = parseMarkdown(markdown);

  return (
    <div className={className}>
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          const headingClass = headingClassForLevel(block.level);
          return (
            <h4 className={headingClass} key={`${block.type}-${index}`}>
              <InlineMarkdown text={block.text} />
            </h4>
          );
        }

        if (block.type === "list") {
          const ListTag = block.ordered ? "ol" : "ul";
          return (
            <ListTag
              className={
                block.ordered
                  ? "list-decimal space-y-2 pl-5 text-current"
                  : "list-disc space-y-2 pl-5 text-current"
              }
              key={`${block.type}-${index}`}
            >
              {block.items.map((item, itemIndex) => (
                <li key={`${item}-${itemIndex}`}>
                  <InlineMarkdown text={item} />
                </li>
              ))}
            </ListTag>
          );
        }

        return (
          <p className="text-current" key={`${block.type}-${index}`}>
            <InlineMarkdown text={block.text} />
          </p>
        );
      })}
    </div>
  );
}

function parseMarkdown(markdown: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  const paragraph: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  function flushParagraph() {
    if (paragraph.length > 0) {
      blocks.push({ type: "paragraph", text: paragraph.join(" ") });
      paragraph.length = 0;
    }
  }

  function flushList() {
    if (list) {
      blocks.push({ type: "list", ordered: list.ordered, items: list.items });
      list = null;
    }
  }

  for (const rawLine of markdown.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push({ type: "heading", level: heading[1].length, text: heading[2] });
      continue;
    }

    const unordered = line.match(/^[-*]\s+(.+)$/);
    const ordered = line.match(/^\d+\.\s+(.+)$/);
    if (unordered || ordered) {
      flushParagraph();
      const isOrdered = Boolean(ordered);
      if (!list || list.ordered !== isOrdered) {
        flushList();
        list = { ordered: isOrdered, items: [] };
      }
      list.items.push((ordered?.[1] ?? unordered?.[1] ?? "").trim());
      continue;
    }

    flushList();
    paragraph.push(line);
  }

  flushParagraph();
  flushList();
  return blocks;
}

function InlineMarkdown({ text }: { text: string }) {
  const parts = text.split(/(\[[^\]]+\]\([^)]+\)|`[^`]+`|\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong className="font-semibold text-foreground" key={`${part}-${index}`}>
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code
              className="rounded bg-muted px-1 py-0.5 text-xs text-foreground"
              key={`${part}-${index}`}
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
        if (link) {
          return (
            <a
              className="text-primary hover:underline"
              href={link[2]}
              key={`${part}-${index}`}
              rel="noreferrer"
              target="_blank"
            >
              {link[1]}
            </a>
          );
        }
        return part;
      })}
    </>
  );
}

function headingClassForLevel(level: number) {
  if (level === 1) {
    return "text-lg font-semibold leading-7 text-foreground";
  }
  if (level === 2) {
    return "text-base font-semibold leading-7 text-foreground";
  }
  return "text-sm font-semibold leading-6 text-foreground";
}
