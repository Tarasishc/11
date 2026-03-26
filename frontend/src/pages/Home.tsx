import { useState } from 'react';
import { Link } from 'react-router-dom';
import DocumentForm from '../components/DocumentForm';
import { GenerateDocumentResponse } from '../types';

export default function Home() {
  const [lastGenerated, setLastGenerated] = useState<GenerateDocumentResponse | null>(null);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Генерація документів
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Заповніть форму для автоматичної генерації акту або рахунку у форматі PDF
        </p>
      </div>

      {/* Info banner if no contacts */}
      <div className="card p-4 border-l-4 border-l-amber-400 bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800">
        <div className="flex items-start gap-3">
          <svg className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
              Підказка щодо використання
            </p>
            <p className="text-sm text-amber-700 dark:text-amber-300 mt-0.5">
              Для автоматичного заповнення реквізитів у документі спочатку{' '}
              <Link to="/contacts" className="font-medium underline hover:no-underline">
                додайте контакти
              </Link>
              {' '}(постачальників та покупців). Поля ПІБ мають autocomplete.
            </p>
          </div>
        </div>
      </div>

      {/* Form */}
      <DocumentForm onGenerated={setLastGenerated} />

      {/* Quick links */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <Link to="/contacts" className="card p-4 hover:shadow-md transition-shadow flex items-center gap-4">
          <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center text-blue-600 dark:text-blue-400 flex-shrink-0">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <div>
            <p className="font-medium text-gray-900 dark:text-white">Управління контактами</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Постачальники та покупці з реквізитами</p>
          </div>
        </Link>

        <Link to="/history" className="card p-4 hover:shadow-md transition-shadow flex items-center gap-4">
          <div className="w-10 h-10 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center justify-center text-green-600 dark:text-green-400 flex-shrink-0">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <p className="font-medium text-gray-900 dark:text-white">Історія документів</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Всі згенеровані акти та рахунки</p>
          </div>
        </Link>
      </div>
    </div>
  );
}
