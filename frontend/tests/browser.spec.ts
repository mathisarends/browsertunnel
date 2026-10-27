import { expect, test } from "@playwright/test";

test("Lit browser controls, stream, clipboard and page cleanup work with Chromium", async ({
  page,
  context,
}) => {
  const errors: string[] = [];
  const sockets: { closed: boolean }[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("websocket", (socket) => {
    if (!socket.url().includes("/api/browser/ws")) return;
    const state = { closed: false };
    sockets.push(state);
    socket.on("close", () => {
      state.closed = true;
    });
  });
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  const status = page.locator("#active-tab-status");
  await expect(status).toContainText("verbunden");
  await expect(page.getByRole("tab")).toHaveCount(1);
  const address = page.locator("#address-input");
  await address.fill(
    "data:text/html,<title>Lit Canon smoke</title><textarea autofocus></textarea>",
  );
  await address.press("Enter");
  await expect(status).toContainText("Lit Canon smoke · verbunden");
  const canvas = page.locator("#browser-canvas");
  await expect
    .poll(() =>
      canvas.evaluate(
        (element: HTMLCanvasElement) =>
          element.getContext("2d")!.getImageData(0, 0, 1, 1).data[3],
      ),
    )
    .toBe(255);
  await canvas.focus();
  await page.keyboard.type("Lit Canon");
  await page.keyboard.press("Control+a");
  await page.keyboard.press("Control+c");
  await expect
    .poll(() => page.evaluate(() => navigator.clipboard.readText()))
    .toBe("Lit Canon");
  await page.getByRole("button", { name: "Neuen Tab öffnen" }).click();
  await expect(page.getByRole("tab")).toHaveCount(2);
  await expect(page.getByRole("tab", { selected: true })).not.toContainText(
    "Lit Canon smoke",
  );
  await page.getByRole("tab", { selected: true }).getByRole("button").click();
  await expect(page.getByRole("tab")).toHaveCount(1);
  await expect(status).toContainText("Lit Canon smoke");
  await page.getByRole("button", { name: "Clear", exact: true }).click();
  await expect(page.locator("#empty-log")).toBeVisible();
  await page.evaluate(async () => {
    const element = document.querySelector("browser-tunnel-page")!;
    const parent = element.parentElement!;
    element.remove();
    await new Promise((resolve) => setTimeout(resolve, 100));
    parent.append(element);
  });
  await expect.poll(() => sockets.length).toBe(2);
  await expect.poll(() => sockets[0].closed).toBe(true);
  await expect(status).toContainText("verbunden");
  await expect(page.locator("#event-log")).not.toContainText("client.error");
  expect(errors).toEqual([]);
});
