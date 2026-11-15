import { predictPortfolio, type HoldingSeries } from "./portfolioModel";

self.onmessage = (event: MessageEvent<HoldingSeries[]>) => {
  try {
    self.postMessage({ model: predictPortfolio(event.data) });
  } catch (error) {
    self.postMessage({ error: (error as Error).message });
  }
};
