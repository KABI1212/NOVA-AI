import React from "react";

const modelOptions = [
  { value: "gpt-4o-mini", label: "GPT-4o mini (Fast)" },
  { value: "gpt-4o", label: "GPT-4o (Smart)" },
  { value: "claude-sonnet-4-5", label: "Claude Sonnet 4.5" },
  { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
  { value: "meta-llama/llama-3.3-70b-instruct", label: "Llama 3.3 70B" },
  { value: "deepseek-chat", label: "DeepSeek Chat" },
  { value: "qwen-3.5", label: "Qwen 3.5 (via GPT)" },
];

function Topbar({ title, model, onModelChange, onToggleSidebar, tools, onToggleTool }) {
  return (
    <div className="topbar">
      <button className="hbtn" type="button" onClick={onToggleSidebar}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>
      <div className="ttl">{title}</div>
      <div className="mp">
        <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
        </svg>
        <select value={model} onChange={(event) => onModelChange(event.target.value)}>
          {modelOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      <div className="mbs">
        <button
          className={`mb${tools.search ? " on" : ""}`}
          type="button"
          onClick={() => onToggleTool("search")}
        >
          {tools.search ? "Search ON" : "Search"}
        </button>
        <button
          className={`mb${tools.think ? " on" : ""}`}
          type="button"
          onClick={() => onToggleTool("think")}
        >
          {tools.think ? "Think ON" : "Think"}
        </button>
        <button
          className={`mb${tools.agent ? " on" : ""}`}
          type="button"
          onClick={() => onToggleTool("agent")}
        >
          {tools.agent ? "Agent ON" : "Agent"}
        </button>
        <button
          className={`mb${tools.memory ? " on" : ""}`}
          type="button"
          onClick={() => onToggleTool("memory")}
        >
          {tools.memory ? "Memory ON" : "Memory"}
        </button>
      </div>
    </div>
  );
}

export default Topbar;