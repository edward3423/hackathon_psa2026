import { useEffect, type RefObject } from 'react'

/*
 * Publish an element's measured height as a CSS custom property on the root,
 * so layout rules elsewhere can reserve exactly the space it occupies.
 *
 * Two elements pin themselves to the bottom of the viewport - the approval bar
 * and the forecast timeline - and both cover whatever the workspace happens to
 * have scrolled underneath them. The rules that get out of their way need their
 * heights, and those heights are not constants: the approval bar wraps at
 * narrow widths and grows with an error banner, and the timeline's milestone
 * strip rewraps too. A hardcoded pixel value per breakpoint drifts the first
 * time either changes, so it is measured instead.
 *
 * The property is removed on unmount, which makes every dependent rule inert
 * whenever the element is not on screen.
 */
export function usePublishedHeight(
  ref: RefObject<HTMLElement | null>,
  property: `--${string}`,
): void {
  useEffect(() => {
    const element = ref.current
    if (!element) return undefined

    const publish = () => {
      document.documentElement.style.setProperty(
        property,
        `${Math.ceil(element.getBoundingClientRect().height)}px`,
      )
    }

    publish()
    const observer = new ResizeObserver(publish)
    observer.observe(element)
    return () => {
      observer.disconnect()
      document.documentElement.style.removeProperty(property)
    }
  }, [ref, property])
}
