import "./style.css";

function getCanvas(): HTMLCanvasElement {
  const element = document.querySelector<HTMLCanvasElement>("#browser-canvas");

  if (!element) {
    throw new Error("Canvas element not found");
  }

  return element;
}

const canvas = getCanvas();

// A future framecast client can draw decoded frames into this canvas.
export function drawFrame(frame: CanvasImageSource): void {
  const context = canvas.getContext("2d");
  context?.drawImage(frame, 0, 0, canvas.width, canvas.height);
}
