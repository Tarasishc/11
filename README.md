# Генератор фінансових документів (PDF)

Повноцінний веб-додаток для автоматичної генерації фінансових документів (акти та рахунки) у форматі PDF.

## Технологічний стек

| Компонент | Технологія |
|-----------|----------|
| Frontend | React 18 + TypeScript + Tailwind CSS + Vite |
| Backend | Node.js + Express + TypeScript |
| База даних | SQLite (better-sqlite3) |
| PDF | Puppeteer (Headless Chrome) |
| AI | OpenAI GPT-4o (необов'язково) |
| Валідація | Zod |

## Запуск через Docker (найпростіше)

```bash
git clone https://github.com/tarasishc/11.git
cd 11
docker compose up --build
```

Відкрий: **http://localhost:3000**

---

## Локальний запуск (без Docker)

```bash
# 1. Встанови залежності фронтенду та збери
cd frontend
npm install
npm run build

# 2. Запусти бекенд
cd ../backend
cp .env.example .env
npm install
npm start
```

Відкрий: **http://localhost:3000**

> OpenAI ключ необов'язковий — без нього документи генеруються локально.

---

## Використання

1. **Контакти** → Додай постачальника та покупця з реквізитами
2. **Генерація** → Заповни форму → натисни "Згенерувати документ"
3. **Завантаж PDF** → натисни кнопку після генерації
4. **Історія** → всі попередні документи
