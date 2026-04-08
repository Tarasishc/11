# Dreamer Docs

Dreamer Docs — тонкий клієнт для ФОПів, що автоматизує генерацію рахунків-фактур через Make.com. Сайт авторизує користувача через Google OAuth, зберігає контрагентів у Supabase, приймає дані форми та відправляє їх POST-запитом на персональний Make webhook — і повертає готове посилання на Google Doc у папці Google Drive. Уся логіка генерації документів живе в Make, сайт є тонким клієнтом.

## Локальний запуск

```bash
npm install
cp .env.example .env
# Заповніть VITE_SUPABASE_URL та VITE_SUPABASE_ANON_KEY у .env
npm run dev
```

Відкрийте [http://localhost:5173](http://localhost:5173).

## Налаштування Supabase

1. Створіть проєкт на [supabase.com](https://supabase.com)
2. У розділі **Authentication → Providers** увімкніть **Google** (потрібен OAuth Client ID і Secret з [Google Cloud Console](https://console.cloud.google.com))
3. Додайте `http://localhost:5173/login` до **Redirect URLs** у розділі Authentication → URL Configuration
4. Скопіюйте **Project URL** та **anon public key** з **Settings → API** у файл `.env`:
   ```
   VITE_SUPABASE_URL=https://xxxxx.supabase.co
   VITE_SUPABASE_ANON_KEY=eyJhbGci...
   ```
5. Відкрийте **SQL Editor** → **New query** і виконайте весь вміст файлу `supabase/migration.sql` одним запуском

## Активація нового клієнта

Після реєстрації користувача через Google:

1. Відкрийте Supabase Dashboard → **Table Editor** → таблиця `profiles`
2. Знайдіть рядок користувача (ID збігається з `auth.users`)
3. Заповніть поле `webhook_url` — URL вашого Make сценарію (наприклад, `https://hook.eu2.make.com/xxxxxxxx`)
4. Збережіть зміни — користувач одразу отримає доступ до генерації документів

## Контракт Make webhook

Webhook приймає `POST` з `Content-Type: application/json`:

```json
{
  "profile": {
    "id": "uuid",
    "full_name": "Іваненко Іван Іванович",
    "ipn": "1234567890",
    "address": "вул. Хрещатик, 1, м. Київ",
    "bank_name": "АТ КБ «ПриватБанк»",
    "bank_account": "UA213996220000026007233566001",
    "bank_mfo": "305299"
  },
  "counterparty": {
    "id": "uuid",
    "name": "ТОВ «Замовник»",
    "tax_id": "12345678",
    "address": "м. Харків, вул. Сумська, 2",
    "bank_name": "АТ «Ощадбанк»",
    "bank_account": "UA903226690000026001300128064",
    "bank_mfo": "300465"
  },
  "items": [
    {
      "name": "Розробка сайту",
      "quantity": 1,
      "unit": "послуга",
      "price": 15000.00,
      "sum": 15000.00
    }
  ],
  "total": 15000.00,
  "document_type": "invoice"
}
```

Webhook повертає:

```json
{
  "google_doc_url": "https://docs.google.com/document/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit"
}
```

## Структура проєкту

```
src/
├── contexts/AuthContext.tsx   — сесія + профіль + авторизація
├── hooks/
│   ├── useAuth.ts             — re-export з AuthContext
│   └── use-toast.ts           — shadcn toast hook
├── components/
│   ├── ProtectedRoute.tsx     — захист маршрутів
│   ├── DashboardLayout.tsx    — sidebar + Outlet
│   ├── TermsModal.tsx         — модалка умов використання
│   └── ui/                    — shadcn/ui компоненти (без CLI)
├── pages/
│   ├── Login.tsx
│   ├── Onboarding.tsx
│   └── dashboard/
│       ├── Home.tsx
│       ├── CreateDocument.tsx
│       ├── Counterparties.tsx
│       ├── History.tsx
│       ├── Stats.tsx
│       └── Settings.tsx
├── types/database.ts          — типи БД вручну
└── lib/
    ├── supabase.ts            — Supabase client
    └── utils.ts               — cn, formatCurrency, formatDate
```
