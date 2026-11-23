import "@testing-library/jest-dom/vitest";

// jsdom has no IntersectionObserver; framer-motion's whileInView needs one.
class IO {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}
// @ts-expect-error test shim
globalThis.IntersectionObserver = IO;
