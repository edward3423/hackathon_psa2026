import '@testing-library/jest-dom/vitest'

// Polyfills required by @xyflow/react in jsdom.

class ResizeObserverPolyfill {
  observe() {}
  unobserve() {}
  disconnect() {}
}

class DOMMatrixReadOnlyPolyfill {
  m22: number
  constructor(transform?: string) {
    const scale = transform?.match(/scale\(([\d.]+)\)/)?.[1]
    this.m22 = scale !== undefined ? Number(scale) : 1
  }
}

globalThis.ResizeObserver =
  globalThis.ResizeObserver ?? (ResizeObserverPolyfill as unknown as typeof ResizeObserver)
globalThis.DOMMatrixReadOnly =
  globalThis.DOMMatrixReadOnly ??
  (DOMMatrixReadOnlyPolyfill as unknown as typeof DOMMatrixReadOnly)

Object.defineProperties(globalThis.HTMLElement.prototype, {
  offsetHeight: {
    configurable: true,
    get() {
      return parseFloat((this as HTMLElement).style.height) || 600
    },
  },
  offsetWidth: {
    configurable: true,
    get() {
      return parseFloat((this as HTMLElement).style.width) || 800
    },
  },
})
;(globalThis.SVGElement.prototype as unknown as { getBBox: () => DOMRect }).getBBox = () =>
  ({ x: 0, y: 0, width: 0, height: 0 }) as DOMRect
