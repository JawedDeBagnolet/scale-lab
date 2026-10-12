import { InstagramLogo, ThreadsLogo, XLogo, type Icon } from '@phosphor-icons/react'
import type { Platform } from '../types/compte'

export const PLATFORM_META: Record<Platform, { label: string; icon: Icon }> = {
  ig: { label: 'Instagram', icon: InstagramLogo },
  th: { label: 'Threads', icon: ThreadsLogo },
  x: { label: 'X', icon: XLogo },
}

export default function PlatformBadge({ platform, withLabel }: { platform: Platform; withLabel?: boolean }) {
  const meta = PLATFORM_META[platform]
  if (!meta) return null
  const IconCmp = meta.icon
  return (
    <span
      title={meta.label}
      className="inline-flex h-6 items-center gap-1.5 rounded-lg bg-white/5 px-1.5 text-xs font-medium text-muted"
    >
      <IconCmp size={14} />
      {withLabel && meta.label}
    </span>
  )
}
