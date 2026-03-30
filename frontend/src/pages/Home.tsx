import { useState } from 'react';
import { Link } from 'react-router-dom';
import DocumentForm from '../components/DocumentForm';
import { GenerateDocumentResponse } from '../types';

export default function Home() {
  const [, setLastGenerated] = useState<GenerateDocumentResponse | null>(null);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Генерація документів</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Заповніть форму для автоматичної генерації акту або рахунку у форматі PDF</p>
      </div>
      <div className="card p-4 border-l-4 border-l-amber-400 bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800">
        <p className="text-sm text-amber-700 dark:text-amber-300">
          Підказка: спочатку <Link to="/contacts" className="font-medium underline">додай контакти</Link> — тоді реквізити підтягнуться автоматично.
        </p>
      </div>
      <DocumentForm onGenerated={setLastGenerated} />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <Link to="/contacts" className="card p-4 hover:shadow-md transition-shadow flex items-center gap-4">
          <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center text-blue-600 text-xl">👥</div>
          <div><p className="font-medium text-gray-900 dark:text-white">Управління контактами</p><p className="text-sm text-gray-500">Постачальники та покупці з реквізитами</p></div>
        </Link>
        <Link to="/history" className="card p-4 hover:shadow-md transition-shadow flex items-center gap-4">
          <div className="w-10 h-10 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center justify-center text-green-600 text-xl">📋</div>
          <div><p className="font-medium text-gray-900 dark:text-white">Історія документів</p><p className="text-sm text-gray-500">Всі згенеровані акти та рахунки</p></div>
        </Link>
      </div>
    </div>
  );
}
