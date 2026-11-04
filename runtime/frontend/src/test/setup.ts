import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { useCourtStore } from "@/store/courtStore";
import { usePaneStore } from "@/store/paneStore";

// The court store is a module-level singleton, so state leaks between tests
// unless it is reset. A test that passed only because a previous one left a
// verdict behind is worse than no test.
afterEach(() => {
  cleanup();
  useCourtStore.getState().reset();
  // Another module-level singleton: a test that opened the record would
  // otherwise leave it open for the next one.
  usePaneStore.setState({ dissentOpen: false, announcedRun: null });

  // The theme is written onto <html> and persisted, so it outlives a render.
  document.documentElement.removeAttribute("style");
  document.documentElement.removeAttribute("data-theme");
  try {
    localStorage.clear();
  } catch {
    /* ignore */
  }
});
