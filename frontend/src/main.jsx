import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/zito-ui.css";
import { App } from "./App.jsx";
import { StoreProvider } from "./lib/store.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <StoreProvider>
      <App />
    </StoreProvider>
  </StrictMode>,
);
