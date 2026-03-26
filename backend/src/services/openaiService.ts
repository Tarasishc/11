import OpenAI from 'openai';
import { Contact, DocumentItem } from '../types';

// Lazy initialization — avoids crash when OPENAI_API_KEY is not set
let _openai: OpenAI | null = null;
function getOpenAI(): OpenAI {
  if (!_openai) {
    if (!process.env.OPENAI_API_KEY) {
      throw new Error('OPENAI_API_KEY is not configured');
    }
    _openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  }
  return _openai;
}

interface GenerateHtmlParams {
  type: 'Акт' | 'Рахунок';
  items: DocumentItem[];
  client: Contact | null;
  seller: Contact | null;
  city: string;
  contract: string;
  unit: string;
  date: string;
  documentNumber: string;
  totalAmount: number;
}

// Build prompt for GPT-4
function buildPrompt(params: GenerateHtmlParams): string {
  const itemsJson = JSON.stringify(params.items);
  const clientJson = JSON.stringify(params.client || {});
  const sellerJson = JSON.stringify(params.seller || {});

  return `Ти система автоматичної генерації фінансових документів у форматі HTML.

ЗАВДАННЯ: Заповнити готовий HTML-шаблон даними з форми та бази даних.

ВХІДНІ ДАНІ:
- Тип документа: ${params.type}
- Товари/послуги: ${itemsJson}
- Клієнт (Покупець): ${params.client?.fullName || params.items[0]?.name || 'Невідомий'}
- Продавець (Постачальник): ${params.seller?.fullName || 'Невідомий'}
- Місто: ${params.city}
- Договір: ${params.contract || 'усний'}
- Одиниця виміру: ${params.unit || 'послуга'}
- Дата: ${params.date}
- Номер документа: ${params.documentNumber}
- Загальна сума: ${params.totalAmount}

РЕКВІЗИТИ ПРОДАВЦЯ (Постачальник):
${sellerJson}

РЕКВІЗИТИ КЛІЄНТА (Покупець):
${clientJson}

КРОК 1: ПАРСИНГ ДАНИХ
З вхідних даних витягни:
1. Тип документа: Акт або Рахунок
2. Товари: масив {назва, ціна}
3. Клієнт ПІБ
4. Продавець ПІБ
5. Місто
6. Договір (якщо порожньо — "усний")
7. Одиниця виміру (якщо порожньо — "послуга")
8. Дата (якщо порожньо — сьогоднішня ДД.ММ.РРРР)

КРОК 2: ЗАПОВНЕННЯ РЕКВІЗИТІВ
Використай надані реквізити для заповнення шаблону:
- Продавець: ${params.seller?.fullName || '[ПІБ не вказано]'}
- ІПН Продавця: ${params.seller?.inn || '—'}
- IBAN Продавця: ${params.seller?.iban || '—'}
- Банк Продавця: ${params.seller?.bank || '—'}
- Адреса Продавця: ${params.seller?.address || '—'}
- Телефон Продавця: ${params.seller?.phone || '—'}
- Клієнт: ${params.client?.fullName || '[ПІБ не вказано]'}
- ЄДРПОУ Клієнта: ${params.client?.edrpou || '—'}
- IBAN Клієнта: ${params.client?.iban || '—'}
- Банк Клієнта: ${params.client?.bank || '—'}
- Адреса Клієнта: ${params.client?.address || '—'}

КРОК 3: ГЕНЕРАЦІЯ
1. Номер документа: ${params.documentNumber}
2. Загальна сума: ${params.totalAmount} грн
3. Переведи суму прописом ПОВНІСТЮ українською малими літерами (наприклад: "п'ятдесят три тисячі гривень 00 копійок")
4. Створи HTML рядки таблиці товарів у форматі:
<tr><td>[№]</td><td>[НАЗВА]</td><td>1</td><td>[ОДИНИЦЯ]</td><td>[ЦІНА]</td><td>[ЦІНА]</td></tr>

${params.type === 'Акт' ? ACT_TEMPLATE : INVOICE_TEMPLATE}

КРИТИЧНО:
1. Відповідь ТІЛЬКИ HTML без будь-якого тексту, пояснень, без \`\`\`html
2. Продавець = Постачальник, Клієнт = Покупець
3. Суму прописом пиши ПОВНІСТЮ українською малими літерами
4. Номер документа: ${params.documentNumber} (10 цифр)
5. Дата у форматі ДД.ММ.РРРР
6. Прізвище для підпису — перше слово з ПІБ`;
}

const ACT_TEMPLATE = `ШАБЛОН АКТА (використай цей HTML, замінивши плейсхолдери реальними даними):
<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{font-family:Arial,sans-serif;padding:30px;font-size:13px;line-height:1.4}table{border-collapse:collapse;width:100%;margin:15px 0}td,th{border:1px solid #000;padding:6px;font-size:12px}th{background:#f5f5f5;font-weight:bold}.header{display:flex;justify-content:space-between;margin-bottom:25px}.header div{width:48%;text-align:center;font-size:12px}.title{text-align:center;font-weight:bold;font-size:15px;margin:15px 0}.signatures{display:flex;justify-content:space-between;margin-top:25px}.signatures div{width:48%}.footer{margin-top:25px;font-size:11px;line-height:1.6}.right{text-align:right}</style></head><body><div class="header"><div><strong>ЗАТВЕРДЖУЮ</strong><br>Підприємець<br>[ПІБ_ПРОДАВЦЯ]<br><br>___________________________<br>[ПРІЗВИЩЕ_ПРОДАВЦЯ]</div><div><strong>ЗАТВЕРДЖУЮ</strong><br><br>[ПІБ_КЛІЄНТА]<br><br>___________________________<br>[ПРІЗВИЩЕ_КЛІЄНТА]</div></div><div class="title">АКТ надання послуг №[НОМЕР] від [ДАТА]</div><p>Ми, що нижче підписалися, представник Замовника [ПІБ_КЛІЄНТА], з одного боку, і представник Виконавця [ПІБ_ПРОДАВЦЯ], з іншого боку, склали цей акт про те, що на підставі наведених документів:</p><p style="text-align:center"><strong>Договір:</strong> [ДОГОВІР]</p><p>Виконавцем були виконані наступні роботи (надані такі послуги):</p><table><thead><tr><th>№</th><th>Найменування робіт, послуг</th><th>Кіл-сть</th><th>Од.</th><th>Ціна</th><th>Сума</th></tr></thead><tbody>[ТОВАРИ]<tr><td colspan="5" class="right"><strong>Всього:</strong></td><td><strong>[СУМА]</strong></td></tr></tbody></table><p>Загальна вартість робіт (послуг) склала [СУМА_ПРОПИСОМ].</p><p>Замовник претензій по обсягу, якості та строкам виконання робіт (надання послуг) не має.</p><p><strong>Місце складання:</strong> м. [МІСТО]</p><div class="signatures"><div>Від Виконавця*<br><br><br>[ПІБ_ПРОДАВЦЯ]</div><div>Від Замовника<br><br><br>[ПІБ_КЛІЄНТА]</div></div><p style="font-size:10px">* Відповідальні за здійснення господарської операції і правильність її оформлення</p><p>[ДАТА]<span style="float:right">[ДАТА]</span></p><div class="footer"><p>[ПІБ_ПРОДАВЦЯ],<br>код за ДРФО [ІПН_ПРОДАВЦЯ], тел.: [ТЕЛЕФОН_ПРОДАВЦЯ],<br>р/р [IBAN_ПРОДАВЦЯ], у банку [БАНК_ПРОДАВЦЯ],<br>[АДРЕСА_ПРОДАВЦЯ]</p><p>[ПІБ_КЛІЄНТА]<br>код за ЄДРПОУ [ЄДРПОУ_КЛІЄНТА],<br>р/р [IBAN_КЛІЄНТА]<br>в [БАНК_КЛІЄНТА]<br>[АДРЕСА_КЛІЄНТА]</p></div></body></html>`;

const INVOICE_TEMPLATE = `ШАБЛОН РАХУНКУ (використай цей HTML, замінивши плейсхолдери реальними даними):
<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{font-family:Arial,sans-serif;padding:30px;font-size:12px;line-height:1.4}table{border-collapse:collapse;width:100%;margin:15px 0}td,th{border:1px solid #000;padding:6px;font-size:11px}th{background:#f5f5f5;font-weight:bold}.info-box{background:#f9f9f9;border:1px solid #ccc;padding:12px;margin:15px 0;font-size:11px}.title{text-align:center;font-weight:bold;font-size:15px;margin:15px 0}.warning{text-align:center;font-size:10px;font-style:italic;margin-bottom:15px;line-height:1.3}.right{text-align:right}</style></head><body><p class="warning">Увага! Оплата цього рахунку означає погодження з умовами поставки товару. Повідомлення про оплату обов'язкове, в іншому випадку не гарантується наявність товару на складі. Товар відпускається за фактом надходження коштів на р/р Постачальника, самовивозом, за наявності довіреності та паспорта.</p><div class="info-box"><strong>Зразок заповнення платіжного доручення</strong><br><br>Отримувач Фізична особа - підприємець. [ПІБ_ПРОДАВЦЯ]<br>Код [ІПН_ПРОДАВЦЯ]<br>Банк отримувача [БАНК_ПРОДАВЦЯ]<span style="float:right"><strong>КРЕДИТ рах. №</strong><br>[IBAN_ПРОДАВЦЯ]</span></div><div class="title">Рахунок на оплату №[НОМЕР] від [ДАТА]</div><p><strong>Постачальник:</strong> [ПІБ_ПРОДАВЦЯ] Код за ДРФО: [ІПН_ПРОДАВЦЯ]</p><p><strong>Покупець:</strong> [ПІБ_КЛІЄНТА] код за ЄДРПОУ: [ЄДРПОУ_КЛІЄНТА]</p><p><strong>Договір:</strong> [ДОГОВІР]</p><table><thead><tr><th>№</th><th>Найменування робіт, послуг</th><th>Кіл-сть</th><th>Од.</th><th>Ціна без ПДВ</th><th>Сума без ПДВ</th></tr></thead><tbody>[ТОВАРИ]<tr><td colspan="5" class="right"><strong>Всього:</strong></td><td><strong>[СУМА]</strong></td></tr></tbody></table><p><strong>Всього найменувань [КІЛЬКІСТЬ], на суму [СУМА] грн. без ПДВ</strong></p><p><strong>[СУМА_ПРОПИСОМ] без ПДВ</strong></p><br><p><strong>Виписав(ла):</strong> ___________________________</p></body></html>`;

/**
 * Generate document HTML using OpenAI GPT-4
 */
export async function generateDocumentHtml(params: GenerateHtmlParams): Promise<string> {
  const prompt = buildPrompt(params);

  const completion = await getOpenAI().chat.completions.create({
    model: 'gpt-4o',
    messages: [
      {
        role: 'system',
        content: 'Ти система генерації фінансових документів. Відповідай ТІЛЬКИ валідним HTML без жодних пояснень, markdown або додаткового тексту.',
      },
      {
        role: 'user',
        content: prompt,
      },
    ],
    temperature: 0.1,
    max_tokens: 4096,
  });

  const html = completion.choices[0]?.message?.content?.trim() || '';

  // Strip any accidental markdown code fences
  return html
    .replace(/^```html\s*/i, '')
    .replace(/^```\s*/i, '')
    .replace(/\s*```$/i, '')
    .trim();
}

/**
 * Fallback: generate HTML locally without OpenAI (for simple cases)
 */
export function generateDocumentHtmlLocal(params: GenerateHtmlParams): string {
  const { type, items, client, seller, city, contract, unit, date, documentNumber, totalAmount } = params;

  const sellerName = seller?.fullName || 'Не вказано';
  const clientName = client?.fullName || 'Не вказано';
  const sellerLastName = sellerName.split(' ')[0] || '';
  const clientLastName = clientName.split(' ')[0] || '';
  const unitLabel = unit || 'послуга';
  const contractLabel = contract || 'усний';

  const itemRows = items
    .map(
      (item, idx) =>
        `<tr><td>${idx + 1}</td><td>${item.name}</td><td>1</td><td>${unitLabel}</td><td>${item.price.toFixed(2)}</td><td>${item.price.toFixed(2)}</td></tr>`
    )
    .join('');

  const totalStr = totalAmount.toFixed(2);
  const amountInWords = numberToUkrWords(totalAmount);

  if (type === 'Акт') {
    return `<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{font-family:Arial,sans-serif;padding:30px;font-size:13px;line-height:1.4}table{border-collapse:collapse;width:100%;margin:15px 0}td,th{border:1px solid #000;padding:6px;font-size:12px}th{background:#f5f5f5;font-weight:bold}.header{display:flex;justify-content:space-between;margin-bottom:25px}.header div{width:48%;text-align:center;font-size:12px}.title{text-align:center;font-weight:bold;font-size:15px;margin:15px 0}.signatures{display:flex;justify-content:space-between;margin-top:25px}.signatures div{width:48%}.footer{margin-top:25px;font-size:11px;line-height:1.6}.right{text-align:right}</style></head><body><div class="header"><div><strong>ЗАТВЕРДЖУЮ</strong><br>Підприємець<br>${sellerName}<br><br>___________________________<br>${sellerLastName}</div><div><strong>ЗАТВЕРДЖУЮ</strong><br><br>${clientName}<br><br>___________________________<br>${clientLastName}</div></div><div class="title">АКТ надання послуг №${documentNumber} від ${date}</div><p>Ми, що нижче підписалися, представник Замовника ${clientName}, з одного боку, і представник Виконавця ${sellerName}, з іншого боку, склали цей акт про те, що на підставі наведених документів:</p><p style="text-align:center"><strong>Договір:</strong> ${contractLabel}</p><p>Виконавцем були виконані наступні роботи (надані такі послуги):</p><table><thead><tr><th>№</th><th>Найменування робіт, послуг</th><th>Кіл-сть</th><th>Од.</th><th>Ціна</th><th>Сума</th></tr></thead><tbody>${itemRows}<tr><td colspan="5" class="right"><strong>Всього:</strong></td><td><strong>${totalStr}</strong></td></tr></tbody></table><p>Загальна вартість робіт (послуг) склала ${amountInWords}.</p><p>Замовник претензій по обсягу, якості та строкам виконання робіт (надання послуг) не має.</p><p><strong>Місце складання:</strong> м. ${city}</p><div class="signatures"><div>Від Виконавця*<br><br><br>${sellerName}</div><div>Від Замовника<br><br><br>${clientName}</div></div><p style="font-size:10px">* Відповідальні за здійснення господарської операції і правильність її оформлення</p><p>${date}<span style="float:right">${date}</span></p><div class="footer"><p>${sellerName},<br>код за ДРФО ${seller?.inn || '—'}, тел.: ${seller?.phone || '—'},<br>р/р ${seller?.iban || '—'}, у банку ${seller?.bank || '—'},<br>${seller?.address || '—'}</p><p>${clientName}<br>код за ЄДРПОУ ${client?.edrpou || '—'},<br>р/р ${client?.iban || '—'}<br>в ${client?.bank || '—'}<br>${client?.address || '—'}</p></div></body></html>`;
  } else {
    return `<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{font-family:Arial,sans-serif;padding:30px;font-size:12px;line-height:1.4}table{border-collapse:collapse;width:100%;margin:15px 0}td,th{border:1px solid #000;padding:6px;font-size:11px}th{background:#f5f5f5;font-weight:bold}.info-box{background:#f9f9f9;border:1px solid #ccc;padding:12px;margin:15px 0;font-size:11px}.title{text-align:center;font-weight:bold;font-size:15px;margin:15px 0}.warning{text-align:center;font-size:10px;font-style:italic;margin-bottom:15px;line-height:1.3}.right{text-align:right}</style></head><body><p class="warning">Увага! Оплата цього рахунку означає погодження з умовами поставки товару. Повідомлення про оплату обов'язкове, в іншому випадку не гарантується наявність товару на складі. Товар відпускається за фактом надходження коштів на р/р Постачальника, самовивозом, за наявності довіреності та паспорта.</p><div class="info-box"><strong>Зразок заповнення платіжного доручення</strong><br><br>Отримувач Фізична особа - підприємець. ${sellerName}<br>Код ${seller?.inn || '—'}<br>Банк отримувача ${seller?.bank || '—'}<span style="float:right"><strong>КРЕДИТ рах. №</strong><br>${seller?.iban || '—'}</span></div><div class="title">Рахунок на оплату №${documentNumber} від ${date}</div><p><strong>Постачальник:</strong> ${sellerName} Код за ДРФО: ${seller?.inn || '—'}</p><p><strong>Покупець:</strong> ${clientName} код за ЄДРПОУ: ${client?.edrpou || '—'}</p><p><strong>Договір:</strong> ${contractLabel}</p><table><thead><tr><th>№</th><th>Найменування робіт, послуг</th><th>Кіл-сть</th><th>Од.</th><th>Ціна без ПДВ</th><th>Сума без ПДВ</th></tr></thead><tbody>${itemRows}<tr><td colspan="5" class="right"><strong>Всього:</strong></td><td><strong>${totalStr}</strong></td></tr></tbody></table><p><strong>Всього найменувань ${items.length}, на суму ${totalStr} грн. без ПДВ</strong></p><p><strong>${amountInWords} без ПДВ</strong></p><br><p><strong>Виписав(ла):</strong> ___________________________</p></body></html>`;
  }
}

/**
 * Convert number to Ukrainian words
 */
function numberToUkrWords(amount: number): string {
  const [intPart, decPart = '00'] = amount.toFixed(2).split('.');
  const kopecks = decPart.padEnd(2, '0').substring(0, 2);
  const intNum = parseInt(intPart, 10);

  const ones = ['', 'одна', 'дві', 'три', 'чотири', 'п\'ять', 'шість', 'сім', 'вісім', 'дев\'ять'];
  const onesM = ['', 'один', 'два', 'три', 'чотири', 'п\'ять', 'шість', 'сім', 'вісім', 'дев\'ять'];
  const teens = ['десять', 'одинадцять', 'дванадцять', 'тринадцять', 'чотирнадцять', 'п\'ятнадцять', 'шістнадцять', 'сімнадцять', 'вісімнадцять', 'дев\'ятнадцять'];
  const tens = ['', 'десять', 'двадцять', 'тридцять', 'сорок', 'п\'ятдесят', 'шістдесят', 'сімдесят', 'вісімдесят', 'дев\'яносто'];
  const hundreds = ['', 'сто', 'двісті', 'триста', 'чотириста', 'п\'ятсот', 'шістсот', 'сімсот', 'вісімсот', 'дев\'ятсот'];

  function threeDigits(n: number, feminine = false): string {
    if (n === 0) return '';
    const parts: string[] = [];
    const h = Math.floor(n / 100);
    const t = Math.floor((n % 100) / 10);
    const o = n % 10;

    if (h > 0) parts.push(hundreds[h]);
    if (t === 1) {
      parts.push(teens[o]);
    } else {
      if (t > 0) parts.push(tens[t]);
      if (o > 0) parts.push(feminine ? ones[o] : onesM[o]);
    }
    return parts.join(' ');
  }

  function thousands(n: number): string {
    if (n === 0) return 'нуль';
    const parts: string[] = [];

    const mil = Math.floor(n / 1000000);
    const tho = Math.floor((n % 1000000) / 1000);
    const rem = n % 1000;

    if (mil > 0) {
      const milWords = threeDigits(mil, false);
      const milSuffix = mil % 10 === 1 && mil % 100 !== 11 ? 'мільйон' : mil % 10 >= 2 && mil % 10 <= 4 && (mil % 100 < 10 || mil % 100 >= 20) ? 'мільйони' : 'мільйонів';
      parts.push(milWords + ' ' + milSuffix);
    }

    if (tho > 0) {
      const thoWords = threeDigits(tho, true);
      const tho10 = tho % 100;
      const tho1 = tho % 10;
      let thoSuffix: string;
      if (tho10 >= 11 && tho10 <= 19) thoSuffix = 'тисяч';
      else if (tho1 === 1) thoSuffix = 'тисяча';
      else if (tho1 >= 2 && tho1 <= 4) thoSuffix = 'тисячі';
      else thoSuffix = 'тисяч';
      parts.push(thoWords + ' ' + thoSuffix);
    }

    if (rem > 0) {
      parts.push(threeDigits(rem, false));
    }

    return parts.join(' ').trim();
  }

  const intWords = thousands(intNum);
  return `${intWords} гривень ${kopecks} копійок`;
}
