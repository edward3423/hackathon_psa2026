/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Override the API host. Empty keeps requests relative, through the dev proxy. */
  readonly VITE_API_BASE?: string
  /** Path to the official PSA mark, e.g. /psa-logo.svg. Unset shows the text lockup. */
  readonly VITE_PSA_LOGO?: string
  /** Set to '1' when that asset has a white wordmark, so it gets an ink chip. */
  readonly VITE_PSA_LOGO_ON_DARK?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

