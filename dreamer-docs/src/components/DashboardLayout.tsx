import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { FileText, Users, History, BarChart2, Settings, LogOut, PlusCircle } from 'lucide-react'

const navItems = [
  { to: '/dashboard', label: 'Головна', icon: FileText, end: true },
  { to: '/dashboard/create', label: 'Новий документ', icon: PlusCircle, end: false },
  { to: '/dashboard/counterparties', label: 'Контрагенти', icon: Users, end: false },
  { to: '/dashboard/history', label: 'Історія', icon: History, end: false },
  { to: '/dashboard/stats', label: 'Статистика', icon: BarChart2, end: false },
  { to: '/dashboard/settings', label: 'Налаштування', icon: Settings, end: false },
]

export function DashboardLayout() {
  const { user, signOut } = useAuth()

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="w-64 border-r bg-card flex flex-col shrink-0">
        <div className="p-6 border-b">
          <h1 className="text-xl font-bold tracking-tight">Dreamer Docs</h1>
        </div>
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                }`
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t space-y-2">
          <div className="text-xs text-muted-foreground truncate px-1">{user?.email}</div>
          <Button variant="outline" size="sm" className="w-full" onClick={signOut}>
            <LogOut className="h-4 w-4 mr-2" />
            Вийти
          </Button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
