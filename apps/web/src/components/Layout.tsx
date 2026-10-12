import { Outlet, useLocation } from 'react-router-dom'
import Sidebar, { MODULES } from './Sidebar'
import Toaster from './Toaster'

export default function Layout() {
  const { pathname } = useLocation()
  const current = MODULES.find((m) => m.path === pathname)

  return (
    <div className="min-h-screen">
      <Sidebar />
      <div className="pl-60">
        <header className="glass sticky top-0 z-10 flex h-16 items-center border-x-0 border-t-0 px-8">
          <h1 className="text-xl font-bold tracking-tight">{current?.label ?? 'Scale Lab'}</h1>
        </header>
        <main className="p-8">
          <Outlet />
        </main>
      </div>
      <Toaster />
    </div>
  )
}
