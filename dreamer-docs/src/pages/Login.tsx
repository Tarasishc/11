import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { isProfileComplete } from '@/types/database'
import { Button } from '@/components/ui/button'
import { TermsModal } from '@/components/TermsModal'

export function Login() {
  const { session, profile, loading, signInWithGoogle, acceptTerms } = useAuth()
  const navigate = useNavigate()
  const [agreed, setAgreed] = useState(false)
  const [loginLoading, setLoginLoading] = useState(false)
  const [showTermsPreview, setShowTermsPreview] = useState(false)
  const [showTermsAccept, setShowTermsAccept] = useState(false)

  useEffect(() => {
    if (loading) return
    if (!session || !profile) return

    if (!profile.terms_accepted_at) {
      setShowTermsAccept(true)
      return
    }

    if (isProfileComplete(profile)) {
      navigate('/dashboard', { replace: true })
    } else {
      navigate('/onboarding', { replace: true })
    }
  }, [loading, session, profile, navigate])

  const handleLogin = async () => {
    setLoginLoading(true)
    await signInWithGoogle()
    setLoginLoading(false)
  }

  const handleAccepted = async () => {
    await acceptTerms()
    setShowTermsAccept(false)
    navigate('/onboarding', { replace: true })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center space-y-2">
          <div className="flex items-center justify-center mb-4">
            <div className="h-12 w-12 rounded-xl bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-lg">D</span>
            </div>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Dreamer Docs</h1>
          <p className="text-muted-foreground">
            Автоматизована генерація документів для ФОПів через Make.com
          </p>
        </div>

        <div className="space-y-4 rounded-lg border bg-card p-6 shadow-sm">
          <label className="flex items-start gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-gray-300 accent-primary cursor-pointer shrink-0"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
            />
            <span className="text-sm text-muted-foreground leading-relaxed">
              Я ознайомився з{' '}
              <button
                type="button"
                className="text-primary underline underline-offset-4 hover:no-underline"
                onClick={() => setShowTermsPreview(true)}
              >
                умовами використання
              </button>{' '}
              та погоджуюсь з ними
            </span>
          </label>

          <Button
            className="w-full"
            onClick={handleLogin}
            disabled={!agreed || loginLoading}
          >
            {loginLoading ? (
              <span className="flex items-center gap-2">
                <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-current" />
                Перенаправлення...
              </span>
            ) : (
              'Увійти через Google'
            )}
          </Button>
        </div>
      </div>

      <TermsModal
        open={showTermsPreview}
        onClose={() => setShowTermsPreview(false)}
      />

      <TermsModal
        open={showTermsAccept}
        onClose={() => {}}
        onAccepted={handleAccepted}
      />
    </div>
  )
}
