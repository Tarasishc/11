import { useContacts } from '../hooks/useContacts';
import ContactsTable from '../components/ContactsTable';
import { ContactFormData } from '../types';
import toast from 'react-hot-toast';

export default function Contacts() {
  const { contacts, loading, createContact, updateContact, deleteContact } = useContacts();
  const handle = (fn: Function) => async (...args: any[]) => {
    try { await fn(...args); } catch (err: any) { toast.error(err.response?.data?.error || 'Помилка'); throw err; }
  };
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Управління контактами</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Постачальники та покупці з повними реквізитами</p>
      </div>
      <ContactsTable contacts={contacts} loading={loading}
        onCreate={handle(createContact)}
        onEdit={(id: string, data: Partial<ContactFormData>) => handle(updateContact)(id, data)}
        onDelete={handle(deleteContact)} />
    </div>
  );
}
