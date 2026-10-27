import "urlpattern-polyfill";
import "./style.css";
import { html } from "lit";
import { createApp } from "lit-canon-composition";
import { browserFeature } from "./features/browser";

const root = document.querySelector("#app");
if (!root) throw new Error("Application root is missing");

createApp({
  root,
  features: [browserFeature],
  baseTitle: "BrowserTunnel",
  notFound: () =>
    html`<p>Seite nicht gefunden. <a href="/">Zum Browser</a></p>`,
}).start();
