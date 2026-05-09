import { memo, useDeferredValue, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

async function copyToClipboard(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textArea = document.createElement("textarea");
  textArea.value = value;
  textArea.style.position = "fixed";
  textArea.style.left = "-9999px";
  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();
  document.execCommand("copy");
  document.body.removeChild(textArea);
}

function looksLikeStructuredDiagram(value) {
  const code = String(value || "");
  if (!code.trim()) {
    return false;
  }

  const nonEmptyLines = code.split("\n").filter((line) => line.trim());
  if (nonEmptyLines.length < 3) {
    return false;
  }

  let score = 0;

  if (/[\u2500-\u257f]/.test(code)) {
    score += 4;
  }

  if ((code.match(/[|+]/g) || []).length >= 8) {
    score += 2;
  }

  if ((code.match(/(?:<-+>|-+>|<-+|=>|<=|\^| v )/g) || []).length >= 1) {
    score += 1;
  }

  if ((code.match(/^\s*[|+:-]/gm) || []).length >= 3) {
    score += 1;
  }

  return score >= 3;
}

function extractPlainText(value) {
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.map((item) => extractPlainText(item)).join("");
  }

  if (value && typeof value === "object" && "props" in value) {
    return extractPlainText(value.props?.children);
  }

  return "";
}

function looksLikeCodeLine(line) {
  const value = String(line || "").trim();
  if (!value) {
    return false;
  }

  if (
    /^(?:import |export |from |class |public |private |protected |static |const |let |var |function |async |await |if\s*\(|else\b|for\s*\(|while\s*\(|switch\s*\(|case\b|return\b|try\b|catch\b|finally\b|def\b|interface |type |enum |#include |using |package |namespace |\{|\}|\/\/|\/\*|\*\/)/.test(
      value
    )
  ) {
    return true;
  }

  return /[;{}()[\]=<>]/.test(value) && value.length <= 180;
}

function resolvePreferredCopyValue(blockCode, fullContent) {
  const normalizedBlockCode = extractPlainText(blockCode).replace(/\n$/, "");
  const fullText = String(fullContent || "");
  const fencedBlocks = [...fullText.matchAll(/```[^\n]*\n?([\s\S]*?)```/g)];

  if (fencedBlocks.length !== 1) {
    return normalizedBlockCode;
  }

  const fencedCode = String(fencedBlocks[0]?.[1] || "").replace(/\n$/, "");
  if (fencedCode !== normalizedBlockCode) {
    return normalizedBlockCode;
  }

  const outsideContent = fullText
    .replace(/```[^\n]*\n?[\s\S]*?```/g, "\n")
    .split("\n")
    .map((line) => line.replace(/\r/g, ""))
    .filter((line) => line.trim());

  if (!outsideContent.length) {
    return normalizedBlockCode;
  }

  const codeLikeLines = outsideContent.filter(looksLikeCodeLine);
  if (!codeLikeLines.length || codeLikeLines.length !== outsideContent.length) {
    return normalizedBlockCode;
  }

  return [...outsideContent, normalizedBlockCode].join("\n").trim();
}

function normalizeStreamingMarkdown(value) {
  const text = String(value || "");
  if (!text.trim()) {
    return text;
  }

  let normalized = text;
  if ((normalized.match(/```/g) || []).length % 2 === 1) {
    normalized = `${normalized.trimEnd()}\n\`\`\``;
  }
  return normalized;
}

function normalizeHeadingSeparators(value) {
  const lines = String(value || "").split("\n");
  const output = [];

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    output.push(line);

    if (!/^\s{0,3}#{1,4}\s+\S/.test(line)) {
      continue;
    }

    let nextIndex = index + 1;
    while (nextIndex < lines.length && !lines[nextIndex].trim()) {
      nextIndex += 1;
    }

    const nextLine = lines[nextIndex] || "";
    const hasSeparator =
      /^\s{0,3}(?:-{3,}|\*{3,}|_{3,}|[─━═-]{6,})\s*$/.test(nextLine);

    if (!hasSeparator) {
      output.push("", "---", "");
    }
  }

  return output.join("\n");
}

function paragraphClassName(children) {
  const text = extractPlainText(children).trim();
  const lowerText = text.toLowerCase();
  const classes = ["nova-p", "nova-bullet-p"];

  if (/^(?:💡\s*)?example\s*:/i.test(text) || lowerText.startsWith("💡 example")) {
    classes.push("example");
  } else if (/^(?:✨\s*)?(?:important|note)\s*:/i.test(text) || lowerText.startsWith("✨")) {
    classes.push("note");
  } else if (/^(?:📌\s*)?(?:key|important)\s*/i.test(text) || lowerText.startsWith("📌")) {
    classes.push("key");
  }

  return classes.join(" ");
}

function MarkdownCodeBlock({ children, fullContent = "", ...props }) {
  const [copied, setCopied] = useState(false);
  const code = extractPlainText(children).replace(/\n$/, "");
  const isDiagramBlock = looksLikeStructuredDiagram(code);
  const preferredCopyValue = resolvePreferredCopyValue(code, fullContent);

  useEffect(() => {
    if (!copied) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => setCopied(false), 1600);
    return () => window.clearTimeout(timeoutId);
  }, [copied]);

  const handleCopy = async () => {
    try {
      await copyToClipboard(preferredCopyValue);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className={`nova-code-block${isDiagramBlock ? " diagram" : ""}`}>
      <button
        type="button"
        className={`nova-code-copy${copied ? " copied" : ""}`}
        onClick={handleCopy}
        title={copied ? "Copied" : "Copy code"}
        aria-label={copied ? "Copied" : "Copy code"}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="9" width="11" height="11" rx="2" />
          <path d="M5 15V6a2 2 0 0 1 2-2h9" />
        </svg>
      </button>
      <pre
        className="nova-code-pre"
        style={{
          fontFamily: "'Times New Roman', Times, serif",
          whiteSpace: isDiagramBlock ? "pre" : "pre-wrap",
          tabSize: 2,
        }}
      >
        <code {...props}>{code}</code>
      </pre>
    </div>
  );
}

function MarkdownAnswer({ content = "", className = "", streaming = false }) {
  const deferredContent = useDeferredValue(content);
  const normalizedContent = streaming ? normalizeStreamingMarkdown(deferredContent) : content;
  const renderContent = normalizeHeadingSeparators(normalizedContent);
  const rootClassName = `nova-markdown${className ? ` ${className}` : ""}`;
  const Heading = ({ level, className: headingClassName, children }) => {
    const Tag = `h${level}`;
    const toneClassName = level <= 2 ? "nova-heading-main" : "nova-heading-sub";
    return <Tag className={`${headingClassName} ${toneClassName}`}>{children}</Tag>;
  };

  return (
    <div className={rootClassName}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{
          h1: ({ children }) => <Heading level={1} className="nova-h1">{children}</Heading>,
          h2: ({ children }) => <Heading level={2} className="nova-h2">{children}</Heading>,
          h3: ({ children }) => <Heading level={3} className="nova-h3">{children}</Heading>,
          h4: ({ children }) => <Heading level={4} className="nova-h4">{children}</Heading>,
          p: ({ children }) => <p className={paragraphClassName(children)}>{children}</p>,
          ul: ({ children }) => <ul className="nova-list nova-list-unordered">{children}</ul>,
          ol: ({ children }) => <ol className="nova-list nova-list-ordered">{children}</ol>,
          li: ({ children }) => <li className="nova-list-item">{children}</li>,
          strong: ({ children }) => <strong className="nova-strong">{children}</strong>,
          em: ({ children }) => <em className="nova-em">{children}</em>,
          blockquote: ({ children }) => <blockquote className="nova-blockquote">{children}</blockquote>,
          hr: () => <hr className="nova-hr heading-separator" />,
          a: ({ href, children }) =>
            href ? (
              <a className="nova-link" href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            ) : (
              <span className="nova-link">{children}</span>
            ),
          img: ({ src, alt }) =>
            src ? <img className="nova-image" src={src} alt={alt || "Illustration"} loading="lazy" /> : null,
          table: ({ children }) => (
            <div className="nova-table-wrap">
              <table className="nova-table">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="nova-thead">{children}</thead>,
          tbody: ({ children }) => <tbody className="nova-tbody">{children}</tbody>,
          tr: ({ children }) => <tr className="nova-tr">{children}</tr>,
          th: ({ children }) => <th className="nova-th">{children}</th>,
          td: ({ children }) => <td className="nova-td">{children}</td>,
          input: ({ type, checked, ...props }) =>
            type === "checkbox" ? (
              <input
                type="checkbox"
                checked={Boolean(checked)}
                readOnly
                disabled
                className="nova-checkbox"
              />
            ) : (
              <input type={type} {...props} />
            ),
          code({ inline, children, ...props }) {
            if (inline) {
              return (
                <code className="nova-inline-code" {...props}>
                  {children}
                </code>
              );
            }

            return (
              <MarkdownCodeBlock {...props} fullContent={renderContent}>
                {children}
              </MarkdownCodeBlock>
            );
          },
        }}
      >
        {renderContent}
      </ReactMarkdown>
    </div>
  );
}

export default memo(MarkdownAnswer);
