import axios from 'axios';
import { Contact, ContactFormData } from '../types';

const BASE_URL = '/api/contacts';

export const contactsApi = {
  getAll: async (type?: 'Постачальник' | 'Покупець'): Promise<Contact[]> => {
    const params = type ? { type } : {};
    const { data } = await axios.get<Contact[]>(BASE_URL, { params });
    return data;
  },

  getById: async (id: string): Promise<Contact> => {
    const { data } = await axios.get<Contact>(`${BASE_URL}/${id}`);
    return data;
  },

  create: async (contact: ContactFormData): Promise<Contact> => {
    const { data } = await axios.post<Contact>(BASE_URL, contact);
    return data;
  },

  update: async (id: string, contact: Partial<ContactFormData>): Promise<Contact> => {
    const { data } = await axios.put<Contact>(`${BASE_URL}/${id}`, contact);
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await axios.delete(`${BASE_URL}/${id}`);
  },
};
