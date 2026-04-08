import { Navigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { isProfileComplete } from '@/types/database'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { session, profile, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  if (!session) {
    return <Navigate to="/login" replace />
  }

  if (!isProfileComplete(profile)) {
    return <Navigate to="/onboarding" replace />
  }

  return <>{children}</>
}
