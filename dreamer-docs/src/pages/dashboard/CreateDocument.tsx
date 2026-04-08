import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Trash2, Plus, AlertCircle } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { supabase } from '@/lib/supabase'
import type { Counterparty } from '@/types/database'
import { formatCurrency } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/hooks/use-toast'

interface ItemRow {
  id: string
  name: string
  quantity: string
  unit: string
  price: string
  sum: number
}

function emptyItem(): ItemRow {
  return { id: crypto.randomUUID(), name: '', quantity: '', unit: 'шт', price: '', sum: 0 }
}

export function CreateDocument() {
  const { profile } = useAuth()
  const { toast } = useToast()
  const [counterparties, setCounterparties] = useState<Counterparty[]>([])
  const [cpLoading, setCpLoading] = useState(true)
  const [selectedCpId, setSelectedCpId] = useState('')
  const [items, setItems] = useState<ItemRow[]>([emptyItem()])
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    const fetch = async () => {
      const { data } = await supabase
        .from('counterparties')
        .select('*')
        .eq('type', 'buyer')
        .order('name')
      setCounterparties((data as Counterparty[]) ?? [])
      setCpLoading(false)
    }
    fetch()
  }, [])

  const updateItem = (id: string, field: keyof ItemRow, value: string) => {
    setItems((prev) =>
      prev.map((item) => {
        if (item.id !== id) return item
        const updated = { ...item, [field]: value }
        if (field === 'quantity' || field === 'price') {
          const qty = parseFloat(field === 'quantity' ? value : item.quantity) || 0
          const prc = parseFloat(field === 'price' ? value : item.price) || 0
          updated.sum = Math.round(qty * prc * 100) / 100
        }
        return updated
      })
    )
  }

  const removeItem = (id: string) => {
    setItems((prev) => prev.filter((i) => i.id !== id))
  }

  const total = items.reduce((acc, i) => acc + i.sum, 0)

  const selectedCp = counterparties.find((c) => c.id === selectedCpId)

  const canSubmit =
    !!selectedCpId &&
    items.length > 0 &&
    items.every((i) => i.name.trim() && i.quantity && i.price) &&
    !!profile?.webhook_url

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit || !profile || !selectedCp) return

    setSubmitting(true)

    const payload = {
      profile: {
        id: profile.id,
        full_name: profile.full_name,
        ipn: profile.ipn,
        address: profile.address,
        bank_name: profile.bank_name,
        bank_account: profile.bank_account,
        bank_mfo: profile.bank_mfo,
      },
      counterparty: {
        id: selectedCp.id,
        name: selectedCp.name,
        tax_id: selectedCp.tax_id,
        address: selectedCp.address,
        bank_name: selectedCp.bank_name,
        bank_account: selectedCp.bank_account,
        bank_mfo: selectedCp.bank_mfo,
      },
      items: items.map((i) => ({
        name: i.name,
        quantity: parseFloat(i.quantity) || 0,
        unit: i.unit,
        price: parseFloat(i.price) || 0,
        sum: i.sum,
      })),
      total: Math.round(total * 100) / 100,
      document_type: 'invoice',
    }

    try {
      const resp = await fetch(profile.webhook_url!, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!resp.ok) throw new Error(`Помилка сервера: ${resp.status} ${resp.statusText}`)

      const result = await resp.json() as { google_doc_url?: string }
      const docUrl = result.google_doc_url

      if (!docUrl) throw new Error('Webhook не повернув посилання на документ')

      await supabase.from('documents_history').insert({
        user_id: profile.id,
        counterparty_id: selectedCp.id,
        counterparty_name: selectedCp.name,
        document_type: 'invoice',
        total_amount: total,
        google_doc_url: docUrl,
      })

      toast({
        title: 'Документ створено',
        description: (
          <a href={docUrl} target="_blank" rel="noopener noreferrer" className="underline font-medium">
            Відкрити документ →
          </a>
        ) as unknown as string,
      })

      setSelectedCpId('')
      setItems([emptyItem()])
    } catch (err) {
      toast({
        title: 'Помилка генерації',
        description: err instanceof Error ? err.message : 'Невідома помилка',
        variant: 'destructive',
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold">Новий документ</h1>
        <p className="text-muted-foreground">Заповніть дані для генерації рахунку-фактури</p>
      </div>

      {!profile?.webhook_url && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 flex gap-3">
          <AlertCircle className="h-5 w-5 text-yellow-600 shrink-0 mt-0.5" />
          <p className="text-sm text-yellow-800">
            Генерація документів недоступна — акаунт ще не активовано адміністратором.
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Тип документа та контрагент</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Тип документа</Label>
              <Select value="invoice" disabled>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="invoice">Рахунок-фактура</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Покупець *</Label>
              {cpLoading ? (
                <div className="h-10 rounded-md border bg-muted animate-pulse" />
              ) : counterparties.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Список контрагентів порожній.{' '}
                  <Link to="/dashboard/counterparties" className="text-primary underline">
                    Додайте контрагента
                  </Link>
                </p>
              ) : (
                <Select value={selectedCpId} onValueChange={setSelectedCpId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Оберіть покупця..." />
                  </SelectTrigger>
                  <SelectContent>
                    {counterparties.map((cp) => (
                      <SelectItem key={cp.id} value={cp.id}>
                        {cp.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base">Позиції</CardTitle>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setItems((prev) => [...prev, emptyItem()])}
            >
              <Plus className="h-4 w-4 mr-1" />
              Додати позицію
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {items.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                Додайте хоча б одну позицію
              </p>
            )}
            {items.map((item, idx) => (
              <div key={item.id} className="rounded-md border p-3 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-muted-foreground">Позиція {idx + 1}</span>
                  {items.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeItem(item.id)}
                      className="text-muted-foreground hover:text-destructive transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <div className="space-y-2">
                  <Input
                    placeholder="Назва товару / послуги"
                    value={item.name}
                    onChange={(e) => updateItem(item.id, 'name', e.target.value)}
                    required
                  />
                </div>
                <div className="grid grid-cols-4 gap-2">
                  <div className="col-span-1 space-y-1">
                    <Label className="text-xs">Кількість</Label>
                    <Input
                      type="number"
                      min="0"
                      step="any"
                      placeholder="1"
                      value={item.quantity}
                      onChange={(e) => updateItem(item.id, 'quantity', e.target.value)}
                      required
                    />
                  </div>
                  <div className="col-span-1 space-y-1">
                    <Label className="text-xs">Одиниця</Label>
                    <Input
                      placeholder="шт"
                      value={item.unit}
                      onChange={(e) => updateItem(item.id, 'unit', e.target.value)}
                    />
                  </div>
                  <div className="col-span-1 space-y-1">
                    <Label className="text-xs">Ціна, грн</Label>
                    <Input
                      type="number"
                      min="0"
                      step="any"
                      placeholder="0.00"
                      value={item.price}
                      onChange={(e) => updateItem(item.id, 'price', e.target.value)}
                      required
                    />
                  </div>
                  <div className="col-span-1 space-y-1">
                    <Label className="text-xs">Сума, грн</Label>
                    <Input value={item.sum.toFixed(2)} readOnly className="bg-muted" />
                  </div>
                </div>
              </div>
            ))}
            {items.length > 0 && (
              <div className="flex justify-end pt-2">
                <div className="text-right">
                  <div className="text-sm text-muted-foreground">Загальна сума</div>
                  <div className="text-xl font-bold">{formatCurrency(total)}</div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Button
          type="submit"
          className="w-full"
          disabled={!canSubmit || submitting}
          title={
            !profile?.webhook_url
              ? 'Акаунт ще не активовано'
              : !selectedCpId
              ? 'Оберіть контрагента'
              : items.length === 0
              ? 'Додайте позиції'
              : undefined
          }
        >
          {submitting ? (
            <span className="flex items-center gap-2">
              <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-current" />
              Генерується...
            </span>
          ) : (
            'Згенерувати документ'
          )}
        </Button>
      </form>
    </div>
  )
}
