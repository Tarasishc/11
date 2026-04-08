import { useState, useEffect } from 'react'
import { CheckCircle2, Clock } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { supabase } from '@/lib/supabase'
import { formatDateTime } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { useToast } from '@/hooks/use-toast'

export function Settings() {
  const { profile, refreshProfile } = useAuth()
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
    if (!profile) return
    setSubmitting(true)
    const { error } = await supabase
      .from('profiles')
      .update(form)
      .eq('id', profile.id)
    setSubmitting(false)
    if (error) {
      toast({ title: 'Помилка', description: error.message, variant: 'destructive' })
    } else {
      await refreshProfile()
      toast({ title: 'Профіль оновлено' })
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Налаштування</h1>
        <p className="text-muted-foreground">Реквізити вашого ФОПу</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Статус активації</CardTitle>
          <CardDescription>Керується адміністратором через Supabase dashboard</CardDescription>
        </CardHeader>
        <CardContent>
          {profile?.webhook_url ? (
            <div className="flex items-center gap-2 text-green-700">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              <span className="text-sm font-medium">Акаунт активовано</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Clock className="h-5 w-5" />
              <span className="text-sm">Очікує активації від адміністратора</span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Реквізити ФОПу</CardTitle>
          <CardDescription>Ці дані вставляються у кожен згенерований документ</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="s-full-name">ПІБ / Назва ФОП *</Label>
              <Input
                id="s-full-name"
                value={form.full_name}
                onChange={set('full_name')}
                required
                placeholder="Іваненко Іван Іванович"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="s-ipn">ІПН *</Label>
              <Input
                id="s-ipn"
                value={form.ipn}
                onChange={set('ipn')}
                required
                placeholder="1234567890"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="s-address">Адреса реєстрації *</Label>
              <Input
                id="s-address"
                value={form.address}
                onChange={set('address')}
                required
                placeholder="вул. Хрещатик, 1, м. Київ, 01001"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="s-bank-account">Рахунок IBAN *</Label>
              <Input
                id="s-bank-account"
                value={form.bank_account}
                onChange={set('bank_account')}
                required
                placeholder="UA213996220000026007233566001"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="s-bank-name">Назва банку</Label>
                <Input
                  id="s-bank-name"
                  value={form.bank_name}
                  onChange={set('bank_name')}
                  placeholder="АТ КБ «ПриватБанк»"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="s-bank-mfo">МФО банку</Label>
                <Input
                  id="s-bank-mfo"
                  value={form.bank_mfo}
                  onChange={set('bank_mfo')}
                  placeholder="305299"
                />
              </div>
            </div>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Збереження...' : 'Зберегти зміни'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {profile?.terms_accepted_at && (
        <p className="text-xs text-muted-foreground">
          Умови використання прийнято: {formatDateTime(profile.terms_accepted_at)}
        </p>
      )}
    </div>
  )
}
