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
 * A draggable divider. Pointer *capture* keeps sending move events to this element even when the
 * mouse leaves it (or crosses the map iframe-like area), which is what makes dragging feel solid.
 * Arrow keys also work, so it is usable without a mouse.
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
      className={`group relative z-[1100] shrink-0 touch-none bg-slate-200 transition-colors hover:bg-sky-400 focus-visible:bg-sky-400 ${
        vertical ? 'w-1.5 cursor-col-resize' : 'h-1.5 cursor-row-resize'
      }`}
    >
      {/* a larger invisible hit area makes the thin bar easy to grab */}
      <span
        className={`absolute ${vertical ? '-inset-x-1.5 inset-y-0' : '-inset-y-1.5 inset-x-0'}`}
      />
    </div>
  )
}
