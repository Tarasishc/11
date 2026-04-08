import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { isProfileComplete } from '@/types/database'
import { supabase } from '@/lib/supabase'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useToast } from '@/hooks/use-toast'

export function Onboarding() {
  const { session, profile, loading, refreshProfile } = useAuth()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({
    full_name: '',
    ipn: '',
    address: '',
    bank_name: '',
    bank_account: '',
    bank_mfo: '',
  })

  useEffect(() => {
    if (loading) return
    if (!session) {
      navigate('/login', { replace: true })
      return
    }
    if (isProfileComplete(profile)) {
      navigate('/dashboard', { replace: true })
    }
  }, [loading, session, profile, navigate])

  useEffect(() => {
    if (profile) {
      setForm({
        full_name: profile.full_name ?? '',
        ipn: profile.ipn ?? '',
        address: profile.address ?? '',
        bank_name: profile.bank_name ?? '',
        bank_account: profile.bank_account ?? '',
        bank_mfo: profile.bank_mfo ?? '',
      })
    }
  }, [profile])

  const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!session) return
    setSubmitting(true)
    const { error } = await supabase
      .from('profiles')
      .upsert({ id: session.user.id, ...form })
    setSubmitting(false)
    if (error) {
      toast({ title: 'Помилка', description: error.message, variant: 'destructive' })
    } else {
      await refreshProfile()
      navigate('/dashboard', { replace: true })
    }
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
      <div className="w-full max-w-lg space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Налаштування профілю</h1>
          <p className="text-muted-foreground mt-1">
            Заповніть реквізити вашого ФОПу — вони будуть використані у документах
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border bg-card p-6 shadow-sm">
          <div className="space-y-2">
            <Label htmlFor="full_name">ПІБ / Назва ФОП *</Label>
            <Input
              id="full_name"
              value={form.full_name}
              onChange={set('full_name')}
              required
              placeholder="Іваненко Іван Іванович"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="ipn">ІПН *</Label>
            <Input
              id="ipn"
              value={form.ipn}
              onChange={set('ipn')}
              required
              placeholder="1234567890"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="address">Адреса реєстрації *</Label>
            <Input
              id="address"
              value={form.address}
              onChange={set('address')}
              required
              placeholder="вул. Хрещатик, 1, м. Київ, 01001"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="bank_account">Рахунок IBAN *</Label>
            <Input
              id="bank_account"
              value={form.bank_account}
              onChange={set('bank_account')}
              required
              placeholder="UA213996220000026007233566001"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="bank_name">Назва банку</Label>
              <Input
                id="bank_name"
                value={form.bank_name}
                onChange={set('bank_name')}
                placeholder="АТ КБ «ПриватБанк»"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="bank_mfo">МФО банку</Label>
              <Input
                id="bank_mfo"
                value={form.bank_mfo}
                onChange={set('bank_mfo')}
                placeholder="305299"
              />
            </div>
          </div>
          <Button type="submit" className="w-full mt-2" disabled={submitting}>
            {submitting ? 'Збереження...' : 'Зберегти та продовжити'}
          </Button>
        </form>
      </div>
    </div>
  )
}
