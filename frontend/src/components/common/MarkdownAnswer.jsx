import { useEffect, useState } from "react";
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

function MarkdownCodeBlock({ children, ...props }) {
  const [copied, setCopied] = useState(false);
  const code = String(children || "").replace(/\n$/, "");
  const isDiagramBlock = looksLikeStructuredDiagram(code);

  useEffect(() => {
    if (!copied) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => setCopied(false), 1600);
    return () => window.clearTimeout(timeoutId);
  }, [copied]);

  const handleCopy = async () => {
    try {
      await copyToClipboard(code);
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
          fontFamily: "Consolas, 'Courier New', monospace",
          whiteSpace: isDiagramBlock ? "pre" : "pre-wrap",
          tabSize: 2,
        }}
      >
        <code {...props}>{code}</code>
      </pre>
    </div>
  );
}

export default function MarkdownAnswer({ content = "", className = "" }) {
  const rootClassName = `nova-markdown${className ? ` ${className}` : ""}`;

  return (
    <div className={rootClassName}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{
          h1: ({ children }) => <h1 className="nova-h1">{children}</h1>,
          h2: ({ children }) => <h2 className="nova-h2">{children}</h2>,
          h3: ({ children }) => <h3 className="nova-h3">{children}</h3>,
          h4: ({ children }) => <h4 className="nova-h4">{children}</h4>,
          p: ({ children }) => <p className="nova-p">{children}</p>,
          ul: ({ children }) => <ul className="nova-list nova-list-unordered">{children}</ul>,
          ol: ({ children }) => <ol className="nova-list nova-list-ordered">{children}</ol>,
          li: ({ children }) => <li className="nova-list-item">{children}</li>,
          strong: ({ children }) => <strong className="nova-strong">{children}</strong>,
          em: ({ children }) => <em className="nova-em">{children}</em>,
          blockquote: ({ children }) => <blockquote className="nova-blockquote">{children}</blockquote>,
          hr: () => <hr className="nova-hr" />,
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

            return <MarkdownCodeBlock {...props}>{children}</MarkdownCodeBlock>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
