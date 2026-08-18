import '@testing-library/jest-dom/vitest'
import { configure } from '@testing-library/react'

// Every workspace in App.tsx is `lazy()`, so a `findBy*` that lands on a page
// waits for a dynamic import as well as a render. Testing Library's 1 s default
// loses that race on a loaded machine roughly once in ten runs, which reads as
// a flaky assertion rather than as the slow chunk it is. Waiting longer costs
// nothing when the element does appear; a genuine failure still fails.
configure({ asyncUtilTimeout: 5000 })

// Polyfills required by @xyflow/react and recharts in jsdom.

/** jsdom lays nothing out, so measured elements are given a plausible box. */
const MEASURED_BOX = { width: 800, height: 320 }

/** Only an explicit pixel size is a size; `100%` measures nothing in jsdom. */
function pixels(value: string, fallback: number): number {
  return value.endsWith('px') ? parseFloat(value) || fallback : fallback
}

function measuredRect(target: Element): DOMRectReadOnly {
  const element = target as HTMLElement
  const width = pixels(element.style.width, MEASURED_BOX.width)
  const height = pixels(element.style.height, MEASURED_BOX.height)
  return {
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: width,
    bottom: height,
    width,
    height,
    toJSON: () => ({}),
  }
}

/**
 * Reports a size once on observe. Recharts' ResponsiveContainer renders
 * nothing at all until it has measured its box, so a no-op observer would
 * leave every chart test asserting against an empty container.
 */
class ResizeObserverPolyfill {
  constructor(private readonly callback: ResizeObserverCallback) {}

  observe(target: Element) {
    const contentRect = measuredRect(target)
    const entry = {
      target,
      contentRect,
      borderBoxSize: [{ inlineSize: contentRect.width, blockSize: contentRect.height }],
      contentBoxSize: [{ inlineSize: contentRect.width, blockSize: contentRect.height }],
      devicePixelContentBoxSize: [
        { inlineSize: contentRect.width, blockSize: contentRect.height },
      ],
    } as unknown as ResizeObserverEntry
    this.callback([entry], this as unknown as ResizeObserver)
  }

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
      return pixels((this as HTMLElement).style.height, 600)
    },
  },
  offsetWidth: {
    configurable: true,
    get() {
      return pixels((this as HTMLElement).style.width, MEASURED_BOX.width)
    },
  },
})
;(globalThis.SVGElement.prototype as unknown as { getBBox: () => DOMRect }).getBBox = () =>
  ({ x: 0, y: 0, width: 0, height: 0 }) as DOMRect
