import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Contact, ContactFormData } from '../types';

const schema = z.object({
  type: z.enum(['Постачальник', 'Покупець']),
  fullName: z.string().min(2, 'ПІБ обов\'язкове (мін. 2 символи)'),
  inn: z.string().optional().default(''),
  edrpou: z.string().optional().default(''),
  iban: z.string().optional().default(''),
  bank: z.string().optional().default(''),
  address: z.string().optional().default(''),
  phone: z.string().optional().default(''),
  email: z.string().email('Невірний email').optional().or(z.literal('')).default(''),
  group: z.string().optional().default(''),
  additionalCode: z.string().optional().default(''),
});

type FormData = z.infer<typeof schema>;

interface ContactModalProps {
  contact: Contact | null;
  onSave: (data: ContactFormData) => Promise<void>;
  onClose: () => void;
}

export default function ContactModal({ contact, onSave, onClose }: ContactModalProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      type: 'Постачальник',
      fullName: '',
      inn: '',
      edrpou: '',
      iban: '',
      bank: '',
      address: '',
      phone: '',
      email: '',
      group: '',
      additionalCode: '',
    },
  });

  useEffect(() => {
    if (contact) {
      reset({
        type: contact.type,
        fullName: contact.fullName,
        inn: contact.inn || '',
        edrpou: contact.edrpou || '',
        iban: contact.iban || '',
        bank: contact.bank || '',
        address: contact.address || '',
        phone: contact.phone || '',
        email: contact.email || '',
        group: contact.group || '',
        additionalCode: contact.additionalCode || '',
      });
    }
  }, [contact, reset]);

  const onSubmit = async (data: FormData) => {
    await onSave(data as ContactFormData);
  };

  const field = (
    name: keyof FormData,
    label: string,
    placeholder: string,
    type: string = 'text',
    required = false
  ) => (
    <div>
      <label className="label">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      <input
        type={type}
        {...register(name)}
        placeholder={placeholder}
        className={`input-field ${errors[name] ? 'border-red-500 focus:ring-red-500' : ''}`}
      />
      {errors[name] && (
        <p className="mt-1 text-xs text-red-500">{errors[name]?.message as string}</p>
      )}
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-16">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-2xl card max-h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            {contact ? 'Редагувати контакт' : 'Новий контакт'}
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col flex-1 overflow-hidden">
          <div className="p-6 overflow-y-auto flex-1 space-y-4">
            {/* Type */}
            <div>
              <label className="label">Тип <span className="text-red-500">*</span></label>
              <div className="flex gap-3">
                {(['Постачальник', 'Покупець'] as const).map(t => (
                  <label key={t} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      value={t}
                      {...register('type')}
                      className="text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-sm text-gray-700 dark:text-gray-300">{t}</span>
                  </label>
                ))}
              </div>
            </div>

            {field('fullName', 'Повне ПІБ / Назва', 'Іванов Іван Іванович', 'text', true)}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {field('inn', 'ІПН / код ДРФО', '1234567890')}
              {field('edrpou', 'ЄДРПОУ', '12345678')}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="sm:col-span-2">
                {field('iban', 'IBAN (банківський рахунок)', 'UA123456789012345678901234567')}
              </div>
              {field('bank', 'Назва банку', 'АТ КБ "ПриватБанк"')}
            </div>

            {field('address', 'Адреса', 'м. Київ, вул. Хрещатик, 1')}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {field('phone', 'Телефон', '+380991234567', 'tel')}
              {field('email', 'Email', 'example@company.ua', 'email')}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {field('group', 'Група (ФОП)', 'ФОП 2 група')}
              {field('additionalCode', 'Додатковий код', '')}
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 dark:border-gray-700">
            <button type="button" onClick={onClose} className="btn-secondary">
              Скасувати
            </button>
            <button type="submit" disabled={isSubmitting} className="btn-primary">
              {isSubmitting ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Збереження...
                </span>
              ) : (
                contact ? 'Зберегти зміни' : 'Створити контакт'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
