import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import AgentApp from "./AgentApp";
import "./styles.css";
import "./agent-styles.css";

const isAgentWorkspace = window.location.pathname.startsWith("/agent");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {isAgentWorkspace ? <AgentApp /> : <App />}
  </StrictMode>,
);
