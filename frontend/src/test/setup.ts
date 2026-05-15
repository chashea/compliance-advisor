import "@testing-library/jest-dom/vitest";

// jsdom does not implement window.matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// jsdom 29 / vitest 4 stopped exposing localStorage by default in worker
// contexts. Provide a minimal in-memory shim so components reading
// window.localStorage don't crash on import (e.g. ThemeContext).
function createMemoryStorage(): Storage {
  const store: Record<string, string> = {};
  return {
    get length() {
      return Object.keys(store).length;
    },
    clear: () => {
      for (const k of Object.keys(store)) delete store[k];
    },
    getItem: (k: string) => (k in store ? store[k] : null),
    key: (i: number) => Object.keys(store)[i] ?? null,
    removeItem: (k: string) => {
      delete store[k];
    },
    setItem: (k: string, v: string) => {
      store[k] = String(v);
    },
  };
}

if (typeof window.localStorage?.getItem !== "function") {
  Object.defineProperty(window, "localStorage", {
    writable: true,
    configurable: true,
    value: createMemoryStorage(),
  });
}
if (typeof window.sessionStorage?.getItem !== "function") {
  Object.defineProperty(window, "sessionStorage", {
    writable: true,
    configurable: true,
    value: createMemoryStorage(),
  });
}
