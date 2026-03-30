import axios from 'axios';
import { Document, GenerateDocumentRequest, GenerateDocumentResponse } from '../types';
const BASE_URL = '/api/documents';
export const documentsApi = {
  generate: async (data: GenerateDocumentRequest): Promise<GenerateDocumentResponse> =>
    (await axios.post<GenerateDocumentResponse>(`${BASE_URL}/generate`, data)).data,
  getAll: async (params?: { search?: string; type?: string; dateFrom?: string; dateTo?: string }): Promise<Document[]> =>
    (await axios.get<Document[]>(BASE_URL, { params })).data,
  getById: async (id: string): Promise<Document> => (await axios.get<Document>(`${BASE_URL}/${id}`)).data,
};
