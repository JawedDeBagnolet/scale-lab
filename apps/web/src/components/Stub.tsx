import { HourglassMedium } from '@phosphor-icons/react'

export default function Stub({ name }: { name: string }) {
  return (
    <div className="card flex h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <HourglassMedium size={36} className="text-dim" />
      <div className="text-xl font-bold">
        Module <span className="gradient-text">{name}</span>
      </div>
      <div className="text-sm text-muted">A venir</div>
    </div>
  )
}
