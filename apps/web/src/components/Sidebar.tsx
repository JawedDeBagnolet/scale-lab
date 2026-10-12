import { NavLink } from 'react-router-dom'
import {
  Binoculars, ChartLine, ChatsCircle, Crosshair, DeviceMobile, GearSix, GlobeHemisphereWest,
  LinkSimple, ListMagnifyingGlass, PaperPlaneTilt, SlidersHorizontal, SquaresFour, TreeStructure,
  UserCircle, UsersThree, type Icon,
} from '@phosphor-icons/react'

export interface ModuleDef {
  path: string
  label: string
  icon: Icon
}

export const MODULE_GROUPS: { title: string; modules: ModuleDef[] }[] = [
  {
    title: 'Pilotage',
    modules: [
      { path: '/', label: 'Dashboard', icon: SquaresFour },
      { path: '/statistiques', label: 'Statistiques', icon: ChartLine },
      { path: '/logs', label: 'Logs', icon: ListMagnifyingGlass },
    ],
  },
  {
    title: 'Comptes',
    modules: [
      { path: '/comptes', label: 'Comptes', icon: UsersThree },
      { path: '/personas', label: 'Personas', icon: UserCircle },
      { path: '/targets', label: 'Targets', icon: Crosshair },
    ],
  },
  {
    title: 'Contenu',
    modules: [
      { path: '/posting', label: 'Posting', icon: PaperPlaneTilt },
      { path: '/veille', label: 'Veille', icon: Binoculars },
      { path: '/crm', label: 'CRM', icon: ChatsCircle },
      { path: '/liens', label: 'Liens', icon: LinkSimple },
    ],
  },
  {
    title: 'Automatisation',
    modules: [
      { path: '/scenarios', label: 'Scenarios', icon: TreeStructure },
      { path: '/comportements', label: 'Comportements', icon: SlidersHorizontal },
    ],
  },
  {
    title: 'Infrastructure',
    modules: [
      { path: '/proxies', label: 'Proxies', icon: GlobeHemisphereWest },
      { path: '/parc', label: 'Parc iPhone', icon: DeviceMobile },
      { path: '/parametres', label: 'Parametres', icon: GearSix },
    ],
  },
]

export const MODULES: ModuleDef[] = MODULE_GROUPS.flatMap((g) => g.modules)

export default function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-line bg-card">
      <div className="flex h-16 shrink-0 items-center gap-3 px-5">
        <div
          className="flex h-8 w-8 items-center justify-center rounded-lg text-sm font-extrabold"
          style={{ background: 'var(--gradient)' }}
        >
          S
        </div>
        <span className="text-base font-bold tracking-tight">Scale Lab</span>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-4">
        {MODULE_GROUPS.map((group) => (
          <div key={group.title} className="mt-4">
            <div className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-dim">
              {group.title}
            </div>
            {group.modules.map(({ path, label, icon: IconCmp }) => (
              <NavLink
                key={path}
                to={path}
                end={path === '/'}
                className={({ isActive }) =>
                  `flex h-9 items-center gap-3 rounded-lg px-3 text-[13px] font-medium transition-colors ${
                    isActive
                      ? 'bg-accent-1/15 text-white'
                      : 'text-muted hover:bg-white/5 hover:text-white'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <IconCmp size={18} weight="regular" className={isActive ? 'text-accent-1' : ''} />
                    {label}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  )
}
