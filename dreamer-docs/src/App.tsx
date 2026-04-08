import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import { Toaster } from '@/components/ui/toaster'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { DashboardLayout } from '@/components/DashboardLayout'
import { Login } from '@/pages/Login'
import { Onboarding } from '@/pages/Onboarding'
import { Home } from '@/pages/dashboard/Home'
import { CreateDocument } from '@/pages/dashboard/CreateDocument'
import { Counterparties } from '@/pages/dashboard/Counterparties'
import { History } from '@/pages/dashboard/History'
import { Stats } from '@/pages/dashboard/Stats'
import { Settings } from '@/pages/dashboard/Settings'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Home />} />
            <Route path="create" element={<CreateDocument />} />
            <Route path="counterparties" element={<Counterparties />} />
            <Route path="history" element={<History />} />
            <Route path="stats" element={<Stats />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
        <Toaster />
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
