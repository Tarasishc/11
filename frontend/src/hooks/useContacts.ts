import { useState, useEffect, useCallback } from 'react';
import { Contact, ContactFormData } from '../types';
import { contactsApi } from '../api/contactsApi';
import toast from 'react-hot-toast';

// Simple in-memory cache
let contactsCache: Contact[] | null = null;
let cacheTimestamp = 0;
const CACHE_TTL = 60_000; // 1 minute

export function useContacts(type?: 'Постачальник' | 'Покупець') {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchContacts = useCallback(async (forceRefresh = false) => {
    // Use cache if available and not expired (only for unfiltered)
    if (!type && !forceRefresh && contactsCache && Date.now() - cacheTimestamp < CACHE_TTL) {
      setContacts(contactsCache);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await contactsApi.getAll(type);
      setContacts(data);
      if (!type) {
        contactsCache = data;
        cacheTimestamp = Date.now();
      }
    } catch (err: any) {
      const msg = err.response?.data?.error || 'Помилка завантаження контактів';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [type]);

  useEffect(() => {
    fetchContacts();
  }, [fetchContacts]);

  const createContact = async (data: ContactFormData) => {
    const contact = await contactsApi.create(data);
    contactsCache = null; // Invalidate cache
    toast.success('Контакт створено');
    await fetchContacts(true);
    return contact;
  };

  const updateContact = async (id: string, data: Partial<ContactFormData>) => {
    const contact = await contactsApi.update(id, data);
    contactsCache = null;
    toast.success('Контакт оновлено');
    await fetchContacts(true);
    return contact;
  };

  const deleteContact = async (id: string) => {
    await contactsApi.delete(id);
    contactsCache = null;
    toast.success('Контакт видалено');
    await fetchContacts(true);
  };

  return {
    contacts,
    loading,
    error,
    refetch: () => fetchContacts(true),
    createContact,
    updateContact,
    deleteContact,
  };
}
