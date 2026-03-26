import { useState } from 'react';
import { Contact, ContactFormData } from '../types';
import ContactModal from './ContactModal';

interface ContactsTableProps {
  contacts: Contact[];
  loading: boolean;
  onEdit: (id: string, data: Partial<ContactFormData>) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onCreate: (data: ContactFormData) => Promise<void>;
}

export default function ContactsTable({
  contacts,
  loading,
  onEdit,
  onDelete,
  onCreate,
}: ContactsTableProps) {
  const [filterType, setFilterType] = useState<'all' | 'Постачальник' | 'Покупець'>('all');
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editContact, setEditContact] = useState<Contact | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const filtered = contacts.filter(c => {
    const matchType = filterType === 'all' || c.type === filterType;
    const matchSearch =
      !search ||
      c.fullName.toLowerCase().includes(search.toLowerCase()) ||
      c.inn?.includes(search) ||
      c.edrpou?.includes(search) ||
      c.phone?.includes(search) ||
      c.email?.toLowerCase().includes(search.toLowerCase());
    return matchType && matchSearch;
  });

  const handleDelete = async (contact: Contact) => {
    if (!confirm(`Видалити контакт "${contact.fullName}"?`)) return;
    setDeletingId(contact.id);
    try {
      await onDelete(contact.id);
    } finally {
      setDeletingId(null);
    }
  };

  const handleSave = async (data: ContactFormData) => {
    if (editContact) {
      await onEdit(editContact.id, data);
    } else {
      await onCreate(data);
    }
    setModalOpen(false);
    setEditContact(null);
  };

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          {(['all', 'Постачальник', 'Покупець'] as const).map(t => (
            <button
              key={t}
              onClick={() => setFilterType(t)}
              className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-all ${
                filterType === t
                  ? 'bg-primary-100 dark:bg-primary-900/40 text-primary-700 dark:text-primary-300'
                  : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              {t === 'all' ? 'Всі' : t}
              <span className="ml-1 text-xs text-gray-500">
                ({t === 'all' ? contacts.length : contacts.filter(c => c.type === t).length})
              </span>
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Пошук..."
              className="input-field pl-9 py-1.5 text-sm"
            />
          </div>
          <button
            onClick={() => { setEditContact(null); setModalOpen(true); }}
            className="btn-primary whitespace-nowrap"
          >
            + Додати
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin w-6 h-6 border-2 border-primary-600 border-t-transparent rounded-full" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">
            <svg className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <p className="text-sm">Контакти не знайдено</p>
            <button
              onClick={() => { setEditContact(null); setModalOpen(true); }}
              className="mt-3 text-sm text-primary-600 hover:underline"
            >
              Додати перший контакт
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-750">
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400 whitespace-nowrap">Тип</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">ПІБ</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400 hidden md:table-cell">ІПН / ЄДРПОУ</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400 hidden lg:table-cell">IBAN</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400 hidden lg:table-cell">Телефон</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Дії</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {filtered.map(contact => (
                  <tr key={contact.id} className="hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors">
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        contact.type === 'Постачальник'
                          ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                          : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                      }`}>
                        {contact.type}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                      {contact.fullName}
                      {contact.email && (
                        <div className="text-xs text-gray-500 dark:text-gray-400 font-normal">{contact.email}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400 hidden md:table-cell">
                      {contact.inn && <div>ІПН: {contact.inn}</div>}
                      {contact.edrpou && <div>ЄДРПОУ: {contact.edrpou}</div>}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400 hidden lg:table-cell font-mono text-xs">
                      {contact.iban || '—'}
                      {contact.bank && <div className="font-sans text-xs text-gray-400">{contact.bank}</div>}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400 hidden lg:table-cell">
                      {contact.phone || '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => { setEditContact(contact); setModalOpen(true); }}
                          className="p-1.5 text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
                          title="Редагувати"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        <button
                          onClick={() => handleDelete(contact)}
                          disabled={deletingId === contact.id}
                          className="p-1.5 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors disabled:opacity-50"
                          title="Видалити"
                        >
                          {deletingId === contact.id ? (
                            <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                          ) : (
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Contact Modal */}
      {modalOpen && (
        <ContactModal
          contact={editContact}
          onSave={handleSave}
          onClose={() => { setModalOpen(false); setEditContact(null); }}
        />
      )}
    </div>
  );
}
