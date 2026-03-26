import { useState, useEffect } from 'react';
import { Document } from '../types';
import { documentsApi } from '../api/documentsApi';

export default function DocumentHistory() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<'' | 'Акт' | 'Рахунок'>('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const data = await documentsApi.getAll({
        search: search || undefined,
        type: filterType || undefined,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
      });
      setDocuments(data);
    } catch {
      // silent fail
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [search, filterType, dateFrom, dateTo]);

  const totalAmount = documents.reduce((sum, d) => sum + d.amount, 0);

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Пошук за клієнтом, номером..."
              className="input-field pl-9 text-sm"
            />
          </div>

          {/* Type filter */}
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value as '' | 'Акт' | 'Рахунок')}
            className="input-field sm:w-40 text-sm"
          >
            <option value="">Всі типи</option>
            <option value="Акт">Акт</option>
            <option value="Рахунок">Рахунок</option>
          </select>

          {/* Date range */}
          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            className="input-field sm:w-36 text-sm"
            title="Від дати"
          />
          <input
            type="date"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
            className="input-field sm:w-36 text-sm"
            title="До дати"
          />

          <button
            onClick={() => { setSearch(''); setFilterType(''); setDateFrom(''); setDateTo(''); }}
            className="btn-secondary text-sm"
          >
            Скинути
          </button>
        </div>
      </div>

      {/* Stats */}
      {!loading && documents.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Всього документів', value: documents.length, color: 'text-gray-900 dark:text-white' },
            { label: 'Актів', value: documents.filter(d => d.type === 'Акт').length, color: 'text-blue-600 dark:text-blue-400' },
            { label: 'Рахунків', value: documents.filter(d => d.type === 'Рахунок').length, color: 'text-green-600 dark:text-green-400' },
            {
              label: 'Загальна сума',
              value: totalAmount.toLocaleString('uk-UA', { minimumFractionDigits: 2 }) + ' грн',
              color: 'text-primary-600 dark:text-primary-400',
            },
          ].map(stat => (
            <div key={stat.label} className="card p-4">
              <p className="text-xs text-gray-500 dark:text-gray-400">{stat.label}</p>
              <p className={`text-lg font-bold mt-1 ${stat.color}`}>{stat.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin w-6 h-6 border-2 border-primary-600 border-t-transparent rounded-full" />
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">
            <svg className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-sm">Документів не знайдено</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-750">
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">#</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Тип</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Дата</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Клієнт</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400 hidden md:table-cell">Продавець</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Сума</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Статус</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-400">PDF</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {documents.map(doc => (
                  <tr key={doc.id} className="hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-gray-500 dark:text-gray-400">
                      {doc.number}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        doc.type === 'Акт'
                          ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                          : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                      }`}>
                        {doc.type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-700 dark:text-gray-300 whitespace-nowrap">
                      {doc.date}
                    </td>
                    <td className="px-4 py-3 text-gray-900 dark:text-gray-100 max-w-[160px] truncate">
                      {doc.client}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400 max-w-[160px] truncate hidden md:table-cell">
                      {doc.seller}
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">
                      {doc.amount.toLocaleString('uk-UA', { minimumFractionDigits: 2 })} грн
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        doc.status === 'generated'
                          ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300'
                          : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                      }`}>
                        {doc.status === 'generated' ? '✓ Готово' : '✗ Помилка'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <a
                        href={doc.pdfUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-primary-600 dark:text-primary-400 hover:underline text-xs font-medium"
                        title="Завантажити PDF"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        PDF
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
