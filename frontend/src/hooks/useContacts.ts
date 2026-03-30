import { useState, useEffect, useCallback } from 'react';
import { Contact, ContactFormData } from '../types';
import { contactsApi } from '../api/contactsApi';
import toast from 'react-hot-toast';

let contactsCache: Contact[] | null = null;
let cacheTimestamp = 0;
const CACHE_TTL = 60_000;

export function useContacts(type?: 'Постачальник' | 'Покупець') {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchContacts = useCallback(async (forceRefresh = false) => {
    if (!type && !forceRefresh && contactsCache && Date.now() - cacheTimestamp < CACHE_TTL) {
      setContacts(contactsCache); return;
    }
    setLoading(true); setError(null);
    try {
      const data = await contactsApi.getAll(type);
      setContacts(data);
      if (!type) { contactsCache = data; cacheTimestamp = Date.now(); }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Помилка завантаження контактів');
    } finally { setLoading(false); }
  }, [type]);

  useEffect(() => { fetchContacts(); }, [fetchContacts]);

  const createContact = async (data: ContactFormData) => {
    const c = await contactsApi.create(data); contactsCache = null;
    toast.success('Контакт створено'); await fetchContacts(true); return c;
  };
  const updateContact = async (id: string, data: Partial<ContactFormData>) => {
    const c = await contactsApi.update(id, data); contactsCache = null;
    toast.success('Контакт оновлено'); await fetchContacts(true); return c;
  };
  const deleteContact = async (id: string) => {
    await contactsApi.delete(id); contactsCache = null;
    toast.success('Контакт видалено'); await fetchContacts(true);
  };

  return { contacts, loading, error, refetch: () => fetchContacts(true), createContact, updateContact, deleteContact };
}
