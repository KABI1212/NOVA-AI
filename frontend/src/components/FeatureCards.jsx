import React from "react";

const suggestions = [
  {
    label: "Research",
    text: "Explain quantum computing and its real-world uses",
  },
  {
    label: "Code",
    text: "Write a Python script to analyze CSV data with pandas",
  },
  {
    label: "Analyze",
    text: "Pros and cons of microservices vs monolithic architecture",
  },
  {
    label: "Write",
    text: "Draft a professional email requesting a project deadline extension",
  },
  {
    label: "Learn",
    text: "Teach me machine learning step by step from scratch",
  },
  {
    label: "Create",
    text: "Build me a beautiful landing page HTML with dark theme",
  },
];

function FeatureCards({ visible, onSelect }) {
  if (!visible) {
    return null;
  }

  return (
    <div className="feature-cards">
      <div className="sgrid">
        {suggestions.map((item) => (
          <button
            key={item.text}
            className="sc"
            type="button"
            onClick={() => onSelect(item.text)}
          >
            <strong>{item.label}</strong>
            {item.text}
          </button>
        ))}
      </div>
    </div>
  );
}

export default FeatureCards;