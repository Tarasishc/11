import { useState, useEffect } from 'react'
import { subDays, format } from 'date-fns'
import { uk } from 'date-fns/locale'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { supabase } from '@/lib/supabase'
import { formatCurrency } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface DayCount { day: string; count: number }
interface DayAmount { day: string; amount: number }
interface CpAmount { name: string; amount: number }

interface RawDoc {
  created_at: string
  total_amount: number
  counterparty_name: string
}

export function Stats() {
  const [docsByDay, setDocsByDay] = useState<DayCount[]>([])
  const [amountByDay, setAmountByDay] = useState<DayAmount[]>([])
  const [topCounterparties, setTopCounterparties] = useState<CpAmount[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchStats = async () => {
      const thirtyDaysAgo = subDays(new Date(), 30)

      const { data, error: err } = await supabase
        .from('documents_history')
        .select('created_at, total_amount, counterparty_name')
        .gte('created_at', thirtyDaysAgo.toISOString())
        .order('created_at')

      if (err) {
        setError(err.message)
        setLoading(false)
        return
      }

      const docs = (data as RawDoc[]) ?? []

      // Group by day
      const dayMap = new Map<string, { count: number; amount: number }>()
      docs.forEach((doc) => {
        const day = format(new Date(doc.created_at), 'dd.MM', { locale: uk })
        const existing = dayMap.get(day) ?? { count: 0, amount: 0 }
        dayMap.set(day, {
          count: existing.count + 1,
          amount: Math.round((existing.amount + Number(doc.total_amount)) * 100) / 100,
        })
      })

      const days = Array.from(dayMap.entries())
      setDocsByDay(days.map(([day, s]) => ({ day, count: s.count })))
      setAmountByDay(days.map(([day, s]) => ({ day, amount: s.amount })))

      // Top 5 counterparties
      const cpMap = new Map<string, number>()
      docs.forEach((doc) => {
        const prev = cpMap.get(doc.counterparty_name) ?? 0
        cpMap.set(doc.counterparty_name, Math.round((prev + Number(doc.total_amount)) * 100) / 100)
      })
      const top5 = Array.from(cpMap.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([name, amount]) => ({ name, amount }))
      setTopCounterparties(top5)

      setLoading(false)
    }

    fetchStats()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-destructive text-sm">{error}</p>
      </div>
    )
  }

  const noData = docsByDay.length === 0

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">Статистика</h1>
        <p className="text-muted-foreground">Останні 30 днів</p>
      </div>

      {noData ? (
        <div className="rounded-lg border bg-card p-12 text-center">
          <p className="text-muted-foreground">
            Ще немає даних за останні 30 днів. Створіть перший документ!
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Кількість документів по днях</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={docsByDay} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip
                    formatter={(value: number) => [value, 'Документів']}
                    contentStyle={{ fontSize: 12 }}
                  />
                  <Bar dataKey="count" fill="hsl(var(--primary))" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Сума по днях</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={amountByDay} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}к`} />
                  <Tooltip
                    formatter={(value: number) => [formatCurrency(value), 'Сума']}
                    contentStyle={{ fontSize: 12 }}
                  />
                  <Bar dataKey="amount" fill="hsl(var(--primary) / 0.7)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {topCounterparties.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Топ-5 контрагентів за сумою</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={topCounterparties}
                    layout="vertical"
                    margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} className="stroke-muted" />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}к`}
                    />
                    <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 11 }} />
                    <Tooltip
                      formatter={(value: number) => [formatCurrency(value), 'Сума']}
                      contentStyle={{ fontSize: 12 }}
                    />
                    <Bar dataKey="amount" fill="hsl(var(--primary) / 0.85)" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
