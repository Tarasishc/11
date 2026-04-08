import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, PlusCircle, Users, History, BarChart2, ExternalLink } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { supabase } from '@/lib/supabase'
import type { DocumentHistoryRow } from '@/types/database'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function Home() {
  const { profile } = useAuth()
  const navigate = useNavigate()
  const [recentDocs, setRecentDocs] = useState<DocumentHistoryRow[]>([])
  const [docsLoading, setDocsLoading] = useState(true)
  const [docsError, setDocsError] = useState<string | null>(null)

  useEffect(() => {
    const fetch = async () => {
      const { data, error } = await supabase
        .from('documents_history')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(5)
      if (error) setDocsError(error.message)
      else setRecentDocs((data as DocumentHistoryRow[]) ?? [])
      setDocsLoading(false)
    }
    fetch()
  }, [])

  const firstName = profile?.full_name?.split(' ')[0] ?? 'користувачу'

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Привіт, {firstName}!</h1>
        <p className="text-muted-foreground">Ласкаво просимо до Dreamer Docs</p>
      </div>

      {!profile?.webhook_url && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 flex gap-3">
          <AlertCircle className="h-5 w-5 text-yellow-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-yellow-800">
              Акаунт очікує активації
            </p>
            <p className="text-sm text-yellow-700 mt-0.5">
              Очікуйте, поки адміністратор активує ваш акаунт. Після активації ви
              зможете генерувати документи.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Button
          onClick={() => navigate('/dashboard/create')}
          disabled={!profile?.webhook_url}
          title={!profile?.webhook_url ? 'Акаунт ще не активовано адміністратором' : undefined}
          className="h-auto py-3 flex-col gap-1"
        >
          <PlusCircle className="h-5 w-5" />
          <span className="text-xs">Новий документ</span>
        </Button>
        <Button
          variant="outline"
          onClick={() => navigate('/dashboard/counterparties')}
          className="h-auto py-3 flex-col gap-1"
        >
          <Users className="h-5 w-5" />
          <span className="text-xs">Контрагенти</span>
        </Button>
        <Button
          variant="outline"
          onClick={() => navigate('/dashboard/history')}
          className="h-auto py-3 flex-col gap-1"
        >
          <History className="h-5 w-5" />
          <span className="text-xs">Історія</span>
        </Button>
        <Button
          variant="outline"
          onClick={() => navigate('/dashboard/stats')}
          className="h-auto py-3 flex-col gap-1"
        >
          <BarChart2 className="h-5 w-5" />
          <span className="text-xs">Статистика</span>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Останні документи</CardTitle>
        </CardHeader>
        <CardContent>
          {docsLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
            </div>
          ) : docsError ? (
            <p className="text-sm text-destructive py-4">{docsError}</p>
          ) : recentDocs.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              Ще немає створених документів
            </p>
          ) : (
            <div className="space-y-2">
              {recentDocs.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between rounded-md border px-4 py-3 gap-4"
                >
                  <div className="min-w-0">
                    <div className="font-medium text-sm truncate">{doc.counterparty_name}</div>
                    <div className="text-xs text-muted-foreground">{formatDateTime(doc.created_at)}</div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-sm font-semibold">{formatCurrency(doc.total_amount)}</span>
                    <a
                      href={doc.google_doc_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:text-primary/80 transition-colors"
                      title="Відкрити документ"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
