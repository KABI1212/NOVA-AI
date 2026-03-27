import React from "react";

import { QUICK_START_CHIPS } from "../constants/chatExperience";

function FeatureCards({ visible, onSelect }) {
  if (!visible) {
    return null;
  }

  return (
    <div className="feature-hub">
      <div className="chip-row">
        {QUICK_START_CHIPS.map((item) => (
          <button key={item.label} className="chip" type="button" onClick={() => onSelect(item.text)}>
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default FeatureCards;
