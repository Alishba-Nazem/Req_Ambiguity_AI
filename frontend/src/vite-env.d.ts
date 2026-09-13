interface ImportMetaEnv {
  readonly VITE_USE_MOCK?: string
}

declare module "pdfjs-dist/build/pdf.worker.min.mjs?url" {
  const src: string
  export default src
}
