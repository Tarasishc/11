# 🚀 Розгортання бота на VPS (Ubuntu) + поетапний запуск

## Мінімальний депозит (важливо!)
Binance: загальний мінімум ордера **5 USDT**, але **BTCUSDT — 50 USDT** нотіоналу.
Бот рахує розмір від ризику; якщо вийде менше мінімуму — він **пропускає угоду** (не оверризикує).

| Депозит | Висновок |
|---|---|
| $100 | ❌ замало — BTC майже не торгуватиметься |
| **$200** | ⚠️ працює **лише при risk 1%** (BTC якраз проходить $50) |
| **$300–500** | ✅ комфортно при risk 0.5–1% на всіх 4 монетах |

% прибутку **не залежить** від суми — $300 і $3000 дають однаковий %. Мінімум потрібен лише щоб ордери проходили. Для форвард-тесту бери **$300–500, risk 0.5%**.

---

## 1. Підготовка VPS
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git
git clone <твій-репозиторій> bot && cd bot
python3 -m venv venv && source venv/bin/activate
pip install ccxt pandas numpy
```

## 2. Налаштування
```bash
cp quant/bot.env.example bot.env
nano bot.env          # заповни TG_TOKEN, TG_CHAT_ID, BINANCE_KEY/SECRET
```
Binance API-ключ: дозволи **тільки «Futures Trade»**, **вивід ВИМКНУТИ**, додай **IP-whitelist** свого VPS.

## 3. Поетапний запуск (НЕ перестрибуй!)
```bash
set -a; source bot.env; set +a            # підвантажити змінні

# А) офлайн-перевірка логіки
python quant/trade_bot.py selftest

# Б) ПАПІР 2–4 тижні (реальні ціни, фейкові угоди)
python quant/trade_bot.py run

# В) TESTNET (BOT_DRY_RUN=0, BOT_TESTNET=1 у bot.env) — реальні ордери, тестові гроші
python quant/trade_bot.py run

# Г) LIVE мала сума (BOT_DRY_RUN=0, BOT_TESTNET=0, BOT_RISK=0.005)
python quant/trade_bot.py run
```

## 4. Автозапуск через systemd (щоб працював 24/7 і перезапускався)
Створи `/etc/systemd/system/tradebot.service`:
```ini
[Unit]
Description=KC+FVG trade bot
After=network-online.target

[Service]
WorkingDirectory=/home/USER/bot
EnvironmentFile=/home/USER/bot/bot.env
ExecStart=/home/USER/bot/venv/bin/python /home/USER/bot/quant/trade_bot.py run
Restart=always
RestartSec=15
User=USER

[Install]
WantedBy=multi-user.target
```
Запуск:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tradebot
sudo systemctl status tradebot          # перевірити
journalctl -u tradebot -f               # дивитись логи наживо
```

## 5. Контроль
- Щоденний звіт прийде в Telegram о `BOT_REPORT_HOUR` UTC.
- Звіт зараз: `python quant/trade_bot.py report`
- Якщо в логах часто `[skip] ... мало капіталу` — підніми депозит або risk.
- Kill-switch (денний збиток >10%) сам зупинить входи й напише в TG.

## ⚠️ Правила
1. **Не йди на LIVE, поки папір (крок Б) не дасть ~+0.2R за 30+ угод.**
2. Стартуй з **risk 0.5%** і суми, яку **не страшно втратити**.
3. Тримай трохи **BNB** на акаунті — комісії на −10%.
4. Перший тиждень live — **дивись кожен звіт**, звіряй угоди бота з графіком.
