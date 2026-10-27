import { html } from "lit";
import { defineFeature, definePage, provide } from "lit-canon-composition";
import {
  BrowserSessionService,
  browserSessionContext,
} from "./session-service";

const browserPage = definePage({
  path: "/",
  load: () => import("./browser-page"),
  render: () => html`<browser-tunnel-page></browser-tunnel-page>`,
});

export const browserFeature = defineFeature({
  name: "browser",
  pages: [browserPage],
  providers: [
    provide(browserSessionContext, () => new BrowserSessionService()),
  ],
});
