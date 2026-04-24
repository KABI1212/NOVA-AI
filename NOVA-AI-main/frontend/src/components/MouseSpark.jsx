import React, { useEffect, useRef, useState } from "react";

function MouseSpark() {
  const [sparks, setSparks] = useState([]);
  const idRef = useRef(0);
  const lastRef = useRef(0);

  useEffect(() => {
    const handleMove = (event) => {
      const now = performance.now();
      if (now - lastRef.current < 40) {
        return;
      }
      lastRef.current = now;

      const id = idRef.current++;
      const size = 6 + Math.random() * 8;
      const spark = {
        id,
        x: event.clientX,
        y: event.clientY,
        size,
      };

      setSparks((prev) => [...prev, spark]);
      setTimeout(() => {
        setSparks((prev) => prev.filter((item) => item.id !== id));
      }, 500);
    };

    window.addEventListener("mousemove", handleMove);
    return () => window.removeEventListener("mousemove", handleMove);
  }, []);

  return (
    <div className="spark-layer">
      {sparks.map((spark) => (
        <span
          key={spark.id}
          className="spark"
          style={{
            left: spark.x,
            top: spark.y,
            width: spark.size,
            height: spark.size,
          }}
        />
      ))}
    </div>
  );
}

export default MouseSpark;