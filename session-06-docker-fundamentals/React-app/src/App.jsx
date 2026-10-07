import React, { useState } from "react";

export default function App() {
  const [count, setCount] = useState(0);
  return (
    <div style={{ fontFamily: "sans-serif", textAlign: "center", marginTop: 80 }}>
      <h1>Hello World from React + Docker!</h1>
      <p>Built with Vite, served by Nginx inside a container.</p>
      <button onClick={() => setCount(count + 1)}>Clicked {count} times</button>
    </div>
  );
}
