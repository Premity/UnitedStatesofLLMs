import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { useCourtStore } from "@/store/courtStore";

// The court store is a module-level singleton, so state leaks between tests
// unless it is reset. A test that passed only because a previous one left a
// verdict behind is worse than no test.
afterEach(() => {
  cleanup();
  useCourtStore.getState().reset();
});
