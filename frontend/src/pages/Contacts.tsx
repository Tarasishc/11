import { useContacts } from '../hooks/useContacts';
import ContactsTable from '../components/ContactsTable';
import { ContactFormData } from '../types';
import toast from 'react-hot-toast';

export default function Contacts() {
  const { contacts, loading, createContact, updateContact, deleteContact } = useContacts();

  const handleCreate = async (data: ContactFormData) => {
    try {
      await createContact(data);
    } catch (err: any) {
      toast.error(err.response?.data?.error || 'Помилка створення контакту');
      throw err;
    }
  };

  const handleUpdate = async (id: string, data: Partial<ContactFormData>) => {
    try {
      await updateContact(id, data);
    } catch (err: any) {
      toast.error(err.response?.data?.error || 'Помилка оновлення контакту');
      throw err;
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteContact(id);
    } catch (err: any) {
      toast.error(err.response?.data?.error || 'Помилка видалення контакту');
      throw err;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Управління контактами
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Постачальники та покупці з повними реквізитами для документів
        </p>
      </div>

      <ContactsTable
        contacts={contacts}
        loading={loading}
        onCreate={handleCreate}
        onEdit={handleUpdate}
        onDelete={handleDelete}
      />
    </div>
  );
}
