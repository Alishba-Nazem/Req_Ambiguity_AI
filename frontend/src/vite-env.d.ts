interface ImportMetaEnv {
  readonly VITE_USE_MOCK?: string
  /** Hugging Face Space id or URL, e.g. lishyyyy-710/req-ambiguity-ai. No secrets. */
  readonly VITE_HF_SPACE?: string
}

declare module "pdfjs-dist/build/pdf.worker.min.mjs?url" {
  const src: string
  export default src
}
