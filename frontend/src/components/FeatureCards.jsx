import React from "react";

const chips = [
  { label: "Code", text: "Write a clean API in FastAPI" },
  { label: "Write", text: "Draft a professional email" },
  { label: "Learn", text: "Teach me machine learning" },
  { label: "Life stuff", text: "Plan a healthy weekly routine" },
  { label: "Nova's choice", text: "Surprise me with something useful" },
];

function FeatureCards({ visible, onSelect }) {
  if (!visible) {
    return null;
  }

  return (
    <div className="chip-row">
      {chips.map((item) => (
        <button key={item.label} className="chip" type="button" onClick={() => onSelect(item.text)}>
          {item.label}
        </button>
      ))}
    </div>
  );
}

export default FeatureCards;

