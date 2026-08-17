import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import AgentApp from "./AgentApp";
import OperationsApp from "./OperationsApp";
import "./styles.css";
import "./agent-styles.css";
import "./operations-styles.css";

const isAgentWorkspace = window.location.pathname.startsWith("/agent");
const isOperationsWorkspace = window.location.pathname.startsWith("/operations");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {isOperationsWorkspace ? <OperationsApp /> : isAgentWorkspace ? <AgentApp /> : <App />}
  </StrictMode>,
);
