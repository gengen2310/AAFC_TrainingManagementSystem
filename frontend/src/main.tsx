import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/layout.css";
import "./styles/components.css";
import "./styles/print.css";
import "./styles/planning.css";

// Cross-origin tab handoff: when the main TMS opens this tab with #t=<token>,
// store the token in sessionStorage before React renders so the first API call
// has it. The fragment is wiped immediately so it never persists in history.
const _hashFrag = window.location.hash;
if (_hashFrag.startsWith("#t=")) {
  const _params = new URLSearchParams(_hashFrag.slice(1));
  const _tok = _params.get("t") ?? "";
  const _reqYear = _params.get("y");
  if (_tok) sessionStorage.setItem("aafc_token", _tok);
  if (_reqYear && /^\d{4}$/.test(_reqYear)) sessionStorage.setItem("aafc_requested_year", _reqYear);
  history.replaceState(null, "", window.location.pathname + window.location.search);
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>
);
