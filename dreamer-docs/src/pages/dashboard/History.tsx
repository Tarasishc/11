import { useState, useEffect } from 'react'
import { ExternalLink, Search } from 'lucide-react'
import { supabase } from '@/lib/supabase'
import type { DocumentHistoryRow } from '@/types/database'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

const docTypeLabels: Record<string, string> = {
  invoice: 'Рахунок-фактура',
  waybill: 'Накладна',
  contract: 'Договір',
}

export function History() {
  const [documents, setDocuments] = useState<DocumentHistoryRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const fetchDocuments = async (from: string, to: string) => {
    setLoading(true)
    setError(null)

    let query = supabase
      .from('documents_history')
      .select('*')
      .order('created_at', { ascending: false })

    if (from) {
      query = query.gte('created_at', new Date(from).toISOString())
    }
    if (to) {
      const toDate = new Date(to)
      toDate.setDate(toDate.getDate() + 1)
      query = query.lt('created_at', toDate.toISOString())
    }

    const { data, error: err } = await query
    if (err) setError(err.message)
    else setDocuments((data as DocumentHistoryRow[]) ?? [])
    setLoading(false)
  }

  useEffect(() => { fetchDocuments('', '') }, [])

  const handleFilter = (e: React.FormEvent) => {
    e.preventDefault()
    fetchDocuments(dateFrom, dateTo)
  }

  const handleReset = () => {
    setDateFrom('')
    setDateTo('')
    fetchDocuments('', '')
  }

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">Історія документів</h1>
        <p className="text-muted-foreground">Всі згенеровані документи</p>
      </div>

      <form onSubmit={handleFilter} className="flex flex-wrap items-end gap-4 rounded-lg border bg-card p-4">
        <div className="space-y-1.5">
          <Label htmlFor="date-from">Від</Label>
          <Input
            id="date-from"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="w-40"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="date-to">До</Label>
          <Input
            id="date-to"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="w-40"
          />
        </div>
        <div className="flex gap-2">
          <Button type="submit">
            <Search className="h-4 w-4 mr-2" />
            Фільтрувати
          </Button>
          {(dateFrom || dateTo) && (
            <Button type="button" variant="outline" onClick={handleReset}>
              Скинути
            </Button>
          )}
        </div>
      </form>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
            </div>
          ) : error ? (
            <p className="text-sm text-destructive p-6">{error}</p>
          ) : documents.length === 0 ? (
            <p className="text-sm text-muted-foreground p-6 text-center">
              {dateFrom || dateTo ? 'Документів за вказаний період не знайдено' : 'Ще немає створених документів'}
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Дата</TableHead>
                  <TableHead>Контрагент</TableHead>
                  <TableHead>Тип</TableHead>
                  <TableHead className="text-right">Сума</TableHead>
                  <TableHead className="w-[60px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="text-muted-foreground text-sm whitespace-nowrap">
                      {formatDateTime(doc.created_at)}
                    </TableCell>
                    <TableCell className="font-medium">{doc.counterparty_name}</TableCell>
                    <TableCell>
                      <span className="text-xs rounded-full px-2 py-0.5 bg-secondary text-secondary-foreground">
                        {docTypeLabels[doc.document_type] ?? doc.document_type}
                      </span>
                    </TableCell>
                    <TableCell className="text-right font-semibold">
                      {formatCurrency(doc.total_amount)}
                    </TableCell>
                    <TableCell>
                      <a
                        href={doc.google_doc_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-center text-primary hover:text-primary/80 transition-colors"
                        title="Відкрити документ"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
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
