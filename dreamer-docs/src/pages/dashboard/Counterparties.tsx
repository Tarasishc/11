import { useState, useEffect } from 'react'
import { Plus, Pencil, Trash2, X } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { supabase } from '@/lib/supabase'
import type { Counterparty, CounterpartyType } from '@/types/database'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useToast } from '@/hooks/use-toast'

const typeLabels: Record<CounterpartyType, string> = {
  buyer: 'Покупець',
  supplier: 'Постачальник',
}

interface FormState {
  type: CounterpartyType
  name: string
  tax_id: string
  address: string
  bank_name: string
  bank_account: string
  bank_mfo: string
}

function emptyForm(): FormState {
  return { type: 'buyer', name: '', tax_id: '', address: '', bank_name: '', bank_account: '', bank_mfo: '' }
}

export function Counterparties() {
  const { user } = useAuth()
  const { toast } = useToast()
  const [counterparties, setCounterparties] = useState<Counterparty[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(emptyForm())
  const [submitting, setSubmitting] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const fetchAll = async () => {
    const { data, error: err } = await supabase
      .from('counterparties')
      .select('*')
      .order('name')
    if (err) setError(err.message)
    else setCounterparties((data as Counterparty[]) ?? [])
    setLoading(false)
  }

  useEffect(() => { fetchAll() }, [])

  const set = (field: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }))

  const openCreate = () => {
    setEditingId(null)
    setForm(emptyForm())
    setShowForm(true)
  }

  const openEdit = (c: Counterparty) => {
    setEditingId(c.id)
    setForm({
      type: c.type,
      name: c.name,
      tax_id: c.tax_id ?? '',
      address: c.address ?? '',
      bank_name: c.bank_name ?? '',
      bank_account: c.bank_account ?? '',
      bank_mfo: c.bank_mfo ?? '',
    })
    setShowForm(true)
  }

  const closeForm = () => {
    setShowForm(false)
    setEditingId(null)
    setForm(emptyForm())
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user) return
    setSubmitting(true)

    const payload = {
      type: form.type,
      name: form.name,
      tax_id: form.tax_id || null,
      address: form.address || null,
      bank_name: form.bank_name || null,
      bank_account: form.bank_account || null,
      bank_mfo: form.bank_mfo || null,
    }

    const { error: err } = editingId
      ? await supabase.from('counterparties').update(payload).eq('id', editingId)
      : await supabase.from('counterparties').insert({ ...payload, user_id: user.id })

    setSubmitting(false)
    if (err) {
      toast({ title: 'Помилка', description: err.message, variant: 'destructive' })
    } else {
      toast({ title: editingId ? 'Контрагента оновлено' : 'Контрагента додано' })
      closeForm()
      await fetchAll()
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Видалити контрагента? Це не вплине на вже створені документи.')) return
    setDeletingId(id)
    const { error: err } = await supabase.from('counterparties').delete().eq('id', id)
    setDeletingId(null)
    if (err) {
      toast({ title: 'Помилка', description: err.message, variant: 'destructive' })
    } else {
      toast({ title: 'Контрагента видалено' })
      setCounterparties((prev) => prev.filter((c) => c.id !== id))
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Контрагенти</h1>
          <p className="text-muted-foreground">Управління покупцями та постачальниками</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" />
          Додати
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base">
              {editingId ? 'Редагування контрагента' : 'Новий контрагент'}
            </CardTitle>
            <button onClick={closeForm} className="text-muted-foreground hover:text-foreground transition-colors">
              <X className="h-5 w-5" />
            </button>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Тип *</Label>
                  <Select
                    value={form.type}
                    onValueChange={(v) => setForm((f) => ({ ...f, type: v as CounterpartyType }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="buyer">Покупець</SelectItem>
                      <SelectItem value="supplier">Постачальник</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cp-name">Назва *</Label>
                  <Input
                    id="cp-name"
                    value={form.name}
                    onChange={set('name')}
                    required
                    placeholder="ТОВ «Компанія»"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="cp-tax-id">ЄДРПОУ / ІПН</Label>
                  <Input id="cp-tax-id" value={form.tax_id} onChange={set('tax_id')} placeholder="12345678" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cp-address">Адреса</Label>
                  <Input id="cp-address" value={form.address} onChange={set('address')} placeholder="м. Київ, вул..." />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="cp-bank-account">IBAN</Label>
                  <Input id="cp-bank-account" value={form.bank_account} onChange={set('bank_account')} placeholder="UA..." />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cp-bank-name">Банк</Label>
                  <Input id="cp-bank-name" value={form.bank_name} onChange={set('bank_name')} placeholder="ПриватБанк" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cp-bank-mfo">МФО</Label>
                  <Input id="cp-bank-mfo" value={form.bank_mfo} onChange={set('bank_mfo')} placeholder="305299" />
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <Button type="button" variant="outline" onClick={closeForm}>
                  Скасувати
                </Button>
                <Button type="submit" disabled={submitting}>
                  {submitting ? 'Збереження...' : editingId ? 'Зберегти' : 'Додати'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
            </div>
          ) : error ? (
            <p className="text-sm text-destructive p-6">{error}</p>
          ) : counterparties.length === 0 ? (
            <p className="text-sm text-muted-foreground p-6 text-center">
              Список контрагентів порожній. Натисніть «Додати», щоб додати першого.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Назва</TableHead>
                  <TableHead>Тип</TableHead>
                  <TableHead>ЄДРПОУ / ІПН</TableHead>
                  <TableHead>IBAN</TableHead>
                  <TableHead className="w-[100px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {counterparties.map((cp) => (
                  <TableRow key={cp.id}>
                    <TableCell className="font-medium">{cp.name}</TableCell>
                    <TableCell>
                      <span className="text-xs rounded-full px-2 py-0.5 bg-secondary text-secondary-foreground">
                        {typeLabels[cp.type]}
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{cp.tax_id ?? '—'}</TableCell>
                    <TableCell className="text-muted-foreground font-mono text-xs">
                      {cp.bank_account ?? '—'}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => openEdit(cp)}
                          className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                          title="Редагувати"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(cp.id)}
                          disabled={deletingId === cp.id}
                          className="p-1 text-muted-foreground hover:text-destructive transition-colors disabled:opacity-50"
                          title="Видалити"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
