import axios from 'axios';
import { Document, GenerateDocumentRequest, GenerateDocumentResponse } from '../types';

const BASE_URL = '/api/documents';

export const documentsApi = {
  generate: async (data: GenerateDocumentRequest): Promise<GenerateDocumentResponse> => {
    const { data: response } = await axios.post<GenerateDocumentResponse>(
      `${BASE_URL}/generate`,
      data
    );
    return response;
  },

  getAll: async (params?: {
    search?: string;
    type?: string;
    dateFrom?: string;
    dateTo?: string;
  }): Promise<Document[]> => {
    const { data } = await axios.get<Document[]>(BASE_URL, { params });
    return data;
  },

  getById: async (id: string): Promise<Document> => {
    const { data } = await axios.get<Document>(`${BASE_URL}/${id}`);
    return data;
  },
};
