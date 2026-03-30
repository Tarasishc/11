import axios from 'axios';
import { Contact, ContactFormData } from '../types';
const BASE_URL = '/api/contacts';
export const contactsApi = {
  getAll: async (type?: 'Постачальник' | 'Покупець'): Promise<Contact[]> => {
    const { data } = await axios.get<Contact[]>(BASE_URL, { params: type ? { type } : {} });
    return data;
  },
  getById: async (id: string): Promise<Contact> => (await axios.get<Contact>(`${BASE_URL}/${id}`)).data,
  create: async (contact: ContactFormData): Promise<Contact> => (await axios.post<Contact>(BASE_URL, contact)).data,
  update: async (id: string, contact: Partial<ContactFormData>): Promise<Contact> => (await axios.put<Contact>(`${BASE_URL}/${id}`, contact)).data,
  delete: async (id: string): Promise<void> => { await axios.delete(`${BASE_URL}/${id}`); },
};
