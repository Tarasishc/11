# Генератор фінансових документів (PDF)

Повноцінний веб-додаток для автоматичної генерації фінансових документів (акти та рахунки) у форматі PDF з використанням OpenAI GPT-4 та Puppeteer.

## Технологічний стек

| Компонент | Технологія |
|-----------|-----------|
| Frontend | React 18 + TypeScript + Tailwind CSS + Vite |
| Backend | Node.js + Express + TypeScript |
| База даних | SQLite (better-sqlite3) |
| PDF генерація | Puppeteer (Headless Chrome) |
| AI | OpenAI GPT-4o |
| Валідація | Zod (фронт + бек) |
| Форми | React Hook Form |

## Функціонал

### 📄 Генерація документів
- Підтримка двох типів: **Акт надання послуг** та **Рахунок на оплату**
- Динамічне додавання товарів/послуг з автоматичним підрахунком суми
- Autocomplete для вибору продавця та клієнта з бази даних
- Генерація через GPT-4o з fallback на локальний шаблон-движок
- Конвертація HTML → PDF через Puppeteer
- Сума прописом українською

### 👥 Управління контактами
- CRUD операції для постачальників та покупців
- Збереження повних реквізитів: ІПН, ЄДРПОУ, IBAN, банк, адреса, телефон, email
- Фільтрація та пошук
- Кешування на фронтенді

### 📋 Історія документів
- Таблиця всіх згенерованих документів
- Фільтрація за типом, датою, пошук
- Завантаження PDF

### 🎨 UI/UX
- Темна та світла тема
- Responsive дизайн (мобільна версія)
- Індикатори завантаження
- Toast сповіщення

## Запуск через Docker (рекомендовано)

```bash
git clone <repo-url>
cd 11

# Опціонально: вкажіть OpenAI ключ
export OPENAI_API_KEY=sk-...

# Збудувати та запустити
docker compose up --build
```

Відкрий: **http://localhost:3000**

---

## Локальний запуск (без Docker)

### 1. Встановлення та збірка

```bash
cd backend
cp .env.example .env        # відредагуй за потреби
npm install

cd ../frontend
npm install
npm run build               # збирає в backend/public/
```

### 2. Запуск

```bash
cd backend
npm start
```

Відкрий: **http://localhost:3000**

> **OpenAI ключ необов'язковий** — без нього документи генеруються локально.

---

## Режим розробки (hot-reload)

```bash
# Terminal 1
cd backend && npm run dev

# Terminal 2
cd frontend && npm run dev   # → http://localhost:5173
```

## API Endpoints

| Метод | Шлях | Опис |
|-------|------|------|
| `POST` | `/api/documents/generate` | Генерація документа |
| `GET` | `/api/documents` | Список документів |
| `GET` | `/api/documents/:id` | Документ за ID |
| `GET` | `/api/documents/pdf/:filename` | Завантаження PDF |
| `GET` | `/api/contacts` | Список контактів |
| `POST` | `/api/contacts` | Створення контакту |
| `PUT` | `/api/contacts/:id` | Оновлення контакту |
| `DELETE` | `/api/contacts/:id` | Видалення контакту |
| `GET` | `/api/health` | Health check |

### POST /api/documents/generate

```json
{
  "type": "Акт",
  "items": [
    { "name": "Розробка сайту", "price": 15000 }
  ],
  "client": "Іванов Іван Іванович",
  "seller": "Петренко Петро Петрович",
  "city": "Київ",
  "contract": "усний",
  "unit": "послуга",
  "date": "2026-03-26"
}
```

**Response:**
```json
{
  "pdf_url": "/api/documents/pdf/act_1234567890_1711234567.pdf",
  "document_id": "uuid-...",
  "number": "1234567890"
}
```

## Структура проекту

```
/
├── backend/
│   ├── src/
│   │   ├── controllers/     # Request handlers
│   │   ├── models/          # Database operations
│   │   ├── routes/          # Express routes
│   │   ├── services/
│   │   │   ├── database.ts  # SQLite connection
│   │   │   ├── openaiService.ts  # GPT-4 + local template
│   │   │   └── pdfGenerator.ts  # Puppeteer PDF
│   │   ├── types/           # TypeScript types
│   │   └── server.ts        # Express app
│   ├── Dockerfile
│   └── package.json
├── frontend/
│   ├── src/
│   │   ├── api/             # Axios API clients
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom hooks
│   │   ├── pages/           # Page components
│   │   ├── types/           # TypeScript types
│   │   └── App.tsx
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── README.md
```

## Логіка генерації документів

1. Користувач заповнює форму на фронтенді
2. Дані відправляються на `POST /api/documents/generate`
3. Бекенд:
   - Шукає повні реквізити клієнта та продавця в SQLite
   - Генерує випадковий 10-значний номер документа
   - Рахує загальну суму товарів
   - Якщо є `OPENAI_API_KEY` → відправляє промпт у GPT-4o
   - Якщо ні → використовує вбудований шаблон-движок
   - Конвертує HTML → PDF через Puppeteer
   - Зберігає PDF у `uploads/pdfs/`
   - Зберігає метадані в SQLite
4. Фронтенд показує кнопку завантаження PDF

## Розширення (Фаза 3)

Для активації додаткових функцій:

- **Telegram Bot**: додати `TELEGRAM_BOT_TOKEN` у `.env`
- **Email розсилка**: інтегрувати `nodemailer`
- **Масова генерація**: endpoint для CSV upload
- **Редагування шаблонів**: адмін-панель для HTML шаблонів

## Ліцензія

MIT
