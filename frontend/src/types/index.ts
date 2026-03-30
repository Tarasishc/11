export interface Contact {
  id: string;
  type: 'Постачальник' | 'Покупець';
  fullName: string;
  inn: string;
  edrpou: string;
  iban: string;
  bank: string;
  address: string;
  phone: string;
  email: string;
  group: string;
  additionalCode: string;
  createdAt: string;
  updatedAt: string;
}
export interface DocumentItem { name: string; price: number; }
export interface GenerateDocumentRequest {
  type: 'Акт' | 'Рахунок';
  items: DocumentItem[];
  client: string; seller: string; city: string;
  contract?: string; unit?: string; date?: string;
}
export interface GenerateDocumentResponse { pdf_url: string; document_id: string; number: string; }
export interface Document {
  id: string; number: string; type: 'Акт' | 'Рахунок';
  date: string; client: string; seller: string;
  amount: number; pdfUrl: string; status: 'generated' | 'error'; createdAt: string;
}
export type ContactFormData = Omit<Contact, 'id' | 'createdAt' | 'updatedAt'>;
