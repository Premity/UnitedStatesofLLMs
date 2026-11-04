/// <reference types="vite/client" />

/** Build-time flags. `VITE_` prefixed vars are the only ones Vite exposes. */
interface ImportMetaEnv {
  /** "1" plays the fixture instead of calling the API. See api/replay.ts. */
  readonly VITE_REPLAY?: string;
  /** Dev proxy target for /api. Read by vite.config.ts, not by app code. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
