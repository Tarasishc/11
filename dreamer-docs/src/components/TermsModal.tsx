import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

interface TermsModalProps {
  open: boolean
  onClose: () => void
  onAccepted?: () => Promise<void>
}

export function TermsModal({ open, onClose, onAccepted }: TermsModalProps) {
  const [loading, setLoading] = useState(false)

  const handleAccept = async () => {
    if (!onAccepted) return
    setLoading(true)
    await onAccepted()
    setLoading(false)
  }

  const isAcceptMode = !!onAccepted

  return (
    <Dialog open={open} onOpenChange={isAcceptMode ? undefined : (v) => { if (!v) onClose() }}>
      <DialogContent
        className="max-w-2xl max-h-[80vh] flex flex-col"
        hideClose={isAcceptMode}
        onInteractOutside={isAcceptMode ? (e) => e.preventDefault() : undefined}
        onEscapeKeyDown={isAcceptMode ? (e) => e.preventDefault() : undefined}
      >
        <DialogHeader>
          <DialogTitle>Умови використання Dreamer Docs</DialogTitle>
        </DialogHeader>
        <div className="overflow-y-auto flex-1 text-sm space-y-4 text-muted-foreground pr-1">
          <p>
            Ласкаво просимо до Dreamer Docs — сервісу для автоматизованої генерації
            документів для фізичних осіб-підприємців (ФОП).
          </p>
          <p>
            <strong className="text-foreground">1. Обробка персональних даних.</strong>{' '}
            Ваші дані (ПІБ, ІПН, банківські реквізити) зберігаються у захищеній базі
            Supabase і передаються виключно на ваш персональний Make.com webhook для
            генерації документів. Дані не передаються третім особам.
          </p>
          <p>
            <strong className="text-foreground">2. Відповідальність.</strong>{' '}
            Сервіс надається «як є». Адміністратор не несе відповідальності за збитки,
            спричинені помилками у введених даних або недоступністю сторонніх сервісів
            (Google Docs, Make.com).
          </p>
          <p>
            <strong className="text-foreground">3. Активація акаунту.</strong>{' '}
            Після реєстрації ваш акаунт потребує ручної активації адміністратором.
            До активації генерація документів недоступна. Ви отримаєте доступ після
            того, як адміністратор прив'яже ваш акаунт до Make сценарію.
          </p>
          <p>
            <strong className="text-foreground">4. Конфіденційність.</strong>{' '}
            Ми не продаємо, не обмінюємо і не розкриваємо вашу персональну інформацію
            без вашої явної згоди, крім випадків, передбачених законодавством.
          </p>
          <p>
            <strong className="text-foreground">5. Зміни умов.</strong>{' '}
            Адміністратор залишає за собою право оновлювати ці умови. Продовження
            використання сервісу після змін означає вашу згоду з оновленими умовами.
          </p>
          <p>
            <strong className="text-foreground">6. Припинення доступу.</strong>{' '}
            Адміністратор може в будь-який момент припинити доступ до сервісу з
            повідомленням або без нього.
          </p>
        </div>
        <DialogFooter className="pt-4">
          {isAcceptMode ? (
            <Button onClick={handleAccept} disabled={loading}>
              {loading ? 'Збереження...' : 'Прийняти умови та продовжити'}
            </Button>
          ) : (
            <Button variant="outline" onClick={onClose}>
              Закрити
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
