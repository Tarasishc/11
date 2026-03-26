import { useState, useEffect, useRef } from 'react';
import { useForm, useFieldArray, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import toast from 'react-hot-toast';
import { documentsApi } from '../api/documentsApi';
import { contactsApi } from '../api/contactsApi';
import { Contact, GenerateDocumentResponse } from '../types';

const schema = z.object({
  type: z.enum(['Акт', 'Рахунок']),
  items: z.array(z.object({
    name: z.string().min(1, 'Назва обов\'язкова'),
    price: z.coerce.number().positive('Ціна має бути > 0'),
  })).min(1, 'Додайте хоча б один товар'),
  client: z.string().min(1, 'Клієнт обов\'язковий'),
  seller: z.string().min(1, 'Продавець обов\'язковий'),
  city: z.string().min(1, 'Місто обов\'язкове'),
  contract: z.string().optional(),
  unit: z.enum(['шт', 'послуга']),
  date: z.string(),
});

type FormData = z.infer<typeof schema>;

interface AutocompleteProps {
  value: string;
  onChange: (val: string) => void;
  contacts: Contact[];
  placeholder: string;
  error?: string;
}

function Autocomplete({ value, onChange, contacts, placeholder, error }: AutocompleteProps) {
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState(value);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => { setInputValue(value); }, [value]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const filtered = contacts.filter(c =>
    c.fullName.toLowerCase().includes(inputValue.toLowerCase())
  );

  return (
    <div className="relative" ref={ref}>
      <input
        type="text"
        value={inputValue}
        onChange={e => { setInputValue(e.target.value); onChange(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        className={`input-field ${error ? 'border-red-500 focus:ring-red-500' : ''}`}
        autoComplete="off"
      />
      {open && filtered.length > 0 && (
        <ul className="absolute z-10 w-full mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg max-h-48 overflow-auto">
          {filtered.map(c => (
            <li
              key={c.id}
              onMouseDown={() => { onChange(c.fullName); setInputValue(c.fullName); setOpen(false); }}
              className="px-3 py-2 text-sm cursor-pointer hover:bg-primary-50 dark:hover:bg-primary-900/30 flex flex-col"
            >
              <span className="font-medium text-gray-900 dark:text-gray-100">{c.fullName}</span>
              {(c.inn || c.edrpou) && (
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {c.inn ? `ІПН: ${c.inn}` : ''}{c.inn && c.edrpou ? ' | ' : ''}{c.edrpou ? `ЄДРПОУ: ${c.edrpou}` : ''}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
    </div>
  );
}

interface DocumentFormProps {
  onGenerated?: (result: GenerateDocumentResponse) => void;
}

export default function DocumentForm({ onGenerated }: DocumentFormProps) {
  const [generating, setGenerating] = useState(false);
  const [sellers, setSellers] = useState<Contact[]>([]);
  const [clients, setClients] = useState<Contact[]>([]);
  const [lastResult, setLastResult] = useState<GenerateDocumentResponse | null>(null);

  const today = new Date().toISOString().split('T')[0];

  const {
    register,
    control,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      type: 'Акт',
      items: [{ name: '', price: 0 }],
      client: '',
      seller: '',
      city: '',
      contract: '',
      unit: 'послуга',
      date: today,
    },
  });

  const { fields, append, remove } = useFieldArray({ control, name: 'items' });
  const watchedItems = watch('items');

  const totalAmount = watchedItems.reduce((sum, item) => {
    const price = parseFloat(String(item.price)) || 0;
    return sum + price;
  }, 0);

  // Load contacts
  useEffect(() => {
    contactsApi.getAll('Постачальник').then(setSellers).catch(() => {});
    contactsApi.getAll('Покупець').then(setClients).catch(() => {});
  }, []);

  const onSubmit = async (data: FormData) => {
    setGenerating(true);
    setLastResult(null);
    try {
      const result = await documentsApi.generate(data);
      setLastResult(result);
      onGenerated?.(result);
      toast.success(`Документ №${result.number} згенеровано!`);
    } catch (err: any) {
      const msg = err.response?.data?.error || 'Помилка генерації документа';
      toast.error(msg);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      {/* Document type & date */}
      <div className="card p-6">
        <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-4">Основні дані</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Type */}
          <div>
            <label className="label">Тип документа *</label>
            <select {...register('type')} className="input-field">
              <option value="Акт">Акт надання послуг</option>
              <option value="Рахунок">Рахунок на оплату</option>
            </select>
          </div>

          {/* Date */}
          <div>
            <label className="label">Дата *</label>
            <input type="date" {...register('date')} className="input-field" />
          </div>

          {/* Unit */}
          <div>
            <label className="label">Одиниця виміру</label>
            <select {...register('unit')} className="input-field">
              <option value="послуга">послуга</option>
              <option value="шт">шт</option>
            </select>
          </div>

          {/* City */}
          <div>
            <label className="label">Місто *</label>
            <input
              type="text"
              {...register('city')}
              placeholder="Київ"
              className={`input-field ${errors.city ? 'border-red-500' : ''}`}
            />
            {errors.city && <p className="mt-1 text-xs text-red-500">{errors.city.message}</p>}
          </div>
        </div>

        {/* Contract */}
        <div className="mt-4">
          <label className="label">Підстава / Договір</label>
          <input
            type="text"
            {...register('contract')}
            placeholder="усний договір (залиште порожнім)"
            className="input-field"
          />
        </div>
      </div>

      {/* Seller & Client */}
      <div className="card p-6">
        <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-4">Сторони</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="label">Продавець (Постачальник) *</label>
            <Controller
              control={control}
              name="seller"
              render={({ field }) => (
                <Autocomplete
                  value={field.value}
                  onChange={field.onChange}
                  contacts={sellers}
                  placeholder="ПІБ продавця..."
                  error={errors.seller?.message}
                />
              )}
            />
          </div>
          <div>
            <label className="label">Клієнт (Покупець) *</label>
            <Controller
              control={control}
              name="client"
              render={({ field }) => (
                <Autocomplete
                  value={field.value}
                  onChange={field.onChange}
                  contacts={clients}
                  placeholder="ПІБ клієнта..."
                  error={errors.client?.message}
                />
              )}
            />
          </div>
        </div>
      </div>

      {/* Items */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">
            Товари / Послуги
          </h2>
          <button
            type="button"
            onClick={() => append({ name: '', price: 0 })}
            className="btn-secondary text-xs px-3 py-1.5"
          >
            + Додати рядок
          </button>
        </div>

        <div className="space-y-3">
          {/* Header */}
          <div className="hidden sm:grid grid-cols-12 gap-3 text-xs font-medium text-gray-500 dark:text-gray-400 px-1">
            <div className="col-span-1">#</div>
            <div className="col-span-7">Назва</div>
            <div className="col-span-3">Ціна (грн)</div>
            <div className="col-span-1"></div>
          </div>

          {fields.map((field, idx) => (
            <div key={field.id} className="grid grid-cols-12 gap-3 items-start">
              <div className="col-span-1 flex items-center justify-center pt-2 text-sm text-gray-500 dark:text-gray-400 font-medium">
                {idx + 1}
              </div>
              <div className="col-span-7">
                <input
                  {...register(`items.${idx}.name`)}
                  placeholder="Назва товару/послуги"
                  className={`input-field ${errors.items?.[idx]?.name ? 'border-red-500' : ''}`}
                />
                {errors.items?.[idx]?.name && (
                  <p className="mt-1 text-xs text-red-500">{errors.items[idx]?.name?.message}</p>
                )}
              </div>
              <div className="col-span-3">
                <input
                  {...register(`items.${idx}.price`)}
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="0.00"
                  className={`input-field ${errors.items?.[idx]?.price ? 'border-red-500' : ''}`}
                />
                {errors.items?.[idx]?.price && (
                  <p className="mt-1 text-xs text-red-500">{errors.items[idx]?.price?.message}</p>
                )}
              </div>
              <div className="col-span-1 flex items-center justify-center pt-2">
                {fields.length > 1 && (
                  <button
                    type="button"
                    onClick={() => remove(idx)}
                    className="text-red-400 hover:text-red-600 transition-colors p-1"
                    title="Видалити"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Total */}
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
          <div className="text-right">
            <span className="text-sm text-gray-500 dark:text-gray-400">Загальна сума:</span>
            <span className="ml-3 text-lg font-bold text-gray-900 dark:text-white">
              {totalAmount.toLocaleString('uk-UA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} грн
            </span>
          </div>
        </div>

        {errors.items?.root && (
          <p className="mt-2 text-sm text-red-500">{errors.items.root.message}</p>
        )}
      </div>

      {/* Submit */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <button
          type="submit"
          disabled={generating}
          className="btn-primary px-8 py-3 text-base w-full sm:w-auto"
        >
          {generating ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Генерація PDF...
            </span>
          ) : (
            '📄 Згенерувати документ'
          )}
        </button>

        {lastResult && (
          <a
            href={lastResult.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary flex items-center gap-2 w-full sm:w-auto justify-center"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Завантажити PDF №{lastResult.number}
          </a>
        )}
      </div>

      {generating && (
        <div className="card p-4 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0">
              <svg className="animate-spin w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-medium text-blue-800 dark:text-blue-200">Генерація документа...</p>
              <p className="text-xs text-blue-600 dark:text-blue-400">
                GPT-4 заповнює шаблон, Puppeteer конвертує в PDF. Це може зайняти 15-30 секунд.
              </p>
            </div>
          </div>
        </div>
      )}
    </form>
  );
}
