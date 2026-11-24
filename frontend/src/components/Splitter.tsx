import type { KeyboardEvent, PointerEvent, RefObject } from 'react'
import { fractionInRect } from '../lib/layout'

interface Props {
  /** 'vertical' = a vertical bar you drag left/right; 'horizontal' = a horizontal bar you drag up/down. */
  orientation: 'vertical' | 'horizontal'
  /** The element whose size is being divided; the pointer position is measured against it. */
  containerRef: RefObject<HTMLElement | null>
  /** Called with the new position as a fraction (0..1) of the container, from its left/top edge. */
  onChange: (fraction: number) => void
  current: number
  label: string
}

/**
 * A draggable divider: a wide invisible hit area with a thin visible line that lights up on hover.
 * Pointer *capture* keeps move events coming to this element even when the cursor crosses the map,
 * which makes dragging feel solid. Arrow keys also work.
 */
export function Splitter({ orientation, containerRef, onChange, current, label }: Props) {
  const axis = orientation === 'vertical' ? 'x' : 'y'

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId)
    e.preventDefault()
  }
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (!e.currentTarget.hasPointerCapture(e.pointerId)) return // not dragging
    const rect = containerRef.current?.getBoundingClientRect()
    if (rect) onChange(fractionInRect(axis, { x: e.clientX, y: e.clientY }, rect))
  }
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const back = orientation === 'vertical' ? 'ArrowLeft' : 'ArrowUp'
    const fwd = orientation === 'vertical' ? 'ArrowRight' : 'ArrowDown'
    if (e.key === back) onChange(current - 0.02)
    else if (e.key === fwd) onChange(current + 0.02)
    else return
    e.preventDefault()
  }

  const vertical = orientation === 'vertical'
  return (
    <div
      role="separator"
      aria-orientation={orientation}
      aria-label={label}
      aria-valuenow={Math.round(current * 100)}
      tabIndex={0}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onKeyDown={onKeyDown}
      className={`group relative z-[1100] flex shrink-0 touch-none items-center justify-center outline-none ${
        vertical ? 'w-3 cursor-col-resize' : 'h-3 cursor-row-resize'
      }`}
    >
      <span
        className={`rounded-full bg-muted/40 transition-all group-hover:bg-accent group-focus-visible:bg-accent group-active:bg-accent ${
          vertical ? 'h-10 w-1 group-hover:h-16' : 'h-1 w-10 group-hover:w-16'
        }`}
      />
    </div>
  )
}
