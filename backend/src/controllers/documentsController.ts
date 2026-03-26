import { Request, Response } from 'express';
import { z } from 'zod';
import path from 'path';
import * as DocumentModel from '../models/Document';
import * as ContactModel from '../models/Contact';
import { generateDocumentHtml, generateDocumentHtmlLocal } from '../services/openaiService';
import { htmlToPdf, getPdfUrl, readPdfFile } from '../services/pdfGenerator';

const documentItemSchema = z.object({
  name: z.string().min(1, 'Назва товару обов\'язкова'),
  price: z.number().positive('Ціна має бути позитивною'),
});

const generateDocumentSchema = z.object({
  type: z.enum(['Акт', 'Рахунок']),
  items: z.array(documentItemSchema).min(1, 'Потрібен хоча б один товар'),
  client: z.string().min(1, 'Клієнт обов\'язковий'),
  seller: z.string().min(1, 'Продавець обов\'язковий'),
  city: z.string().min(1, 'Місто обов\'язкове'),
  contract: z.string().optional().default('усний'),
  unit: z.string().optional().default('послуга'),
  date: z.string().optional(),
});

/**
 * Generate random 10-digit document number
 */
function generateDocumentNumber(): string {
  return Math.floor(Math.random() * 9000000000 + 1000000000).toString();
}

/**
 * Format date as DD.MM.YYYY
 */
function formatDate(dateStr?: string): string {
  const d = dateStr ? new Date(dateStr) : new Date();
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  return `${day}.${month}.${year}`;
}

export async function generateDocument(req: Request, res: Response): Promise<void> {
  try {
    const result = generateDocumentSchema.safeParse(req.body);
    if (!result.success) {
      res.status(400).json({ error: 'Невалідні дані', details: result.error.flatten() });
      return;
    }

    const { type, items, client, seller, city, contract, unit, date } = result.data;

    // Find contacts in database
    const sellerContact = ContactModel.findContactByNameAndType(seller, 'Постачальник');
    const clientContact = ContactModel.findContactByNameAndType(client, 'Покупець');

    // Calculate total amount
    const totalAmount = items.reduce((sum, item) => sum + item.price, 0);

    // Generate document number and format date
    const documentNumber = generateDocumentNumber();
    const formattedDate = formatDate(date);

    const params = {
      type,
      items,
      client: clientContact,
      seller: sellerContact,
      city,
      contract: contract || 'усний',
      unit: unit || 'послуга',
      date: formattedDate,
      documentNumber,
      totalAmount,
    };

    // Try OpenAI first, fall back to local generation
    let html: string;
    if (process.env.OPENAI_API_KEY && process.env.OPENAI_API_KEY !== 'your_openai_api_key_here') {
      try {
        html = await generateDocumentHtml(params);
      } catch (openaiError: any) {
        console.warn('OpenAI failed, using local template:', openaiError.message);
        html = generateDocumentHtmlLocal(params);
      }
    } else {
      console.log('No OpenAI key configured, using local template');
      html = generateDocumentHtmlLocal(params);
    }

    // Generate PDF
    const filename = `${type === 'Акт' ? 'act' : 'invoice'}_${documentNumber}_${Date.now()}.pdf`;
    await htmlToPdf(html, filename);
    const pdfUrl = getPdfUrl(filename);

    // Save document metadata to database
    const document = DocumentModel.createDocument({
      number: documentNumber,
      type,
      date: formattedDate,
      client: clientContact?.fullName || client,
      seller: sellerContact?.fullName || seller,
      amount: totalAmount,
      pdfUrl,
      status: 'generated',
    });

    res.json({
      pdf_url: pdfUrl,
      document_id: document.id,
      number: documentNumber,
    });
  } catch (error: any) {
    console.error('Document generation error:', error);
    res.status(500).json({ error: 'Помилка генерації документа', details: error.message });
  }
}

export function getDocuments(req: Request, res: Response): void {
  try {
    const { search, type, dateFrom, dateTo } = req.query;

    let documents;
    if (search) {
      documents = DocumentModel.searchDocuments(search as string);
    } else if (type || dateFrom || dateTo) {
      documents = DocumentModel.filterDocuments(
        type as string | undefined,
        dateFrom as string | undefined,
        dateTo as string | undefined
      );
    } else {
      documents = DocumentModel.getAllDocuments();
    }

    res.json(documents);
  } catch (error: any) {
    res.status(500).json({ error: 'Помилка отримання документів', details: error.message });
  }
}

export function getDocument(req: Request, res: Response): void {
  try {
    const document = DocumentModel.getDocumentById(req.params.id);
    if (!document) {
      res.status(404).json({ error: 'Документ не знайдено' });
      return;
    }
    res.json(document);
  } catch (error: any) {
    res.status(500).json({ error: 'Помилка отримання документу', details: error.message });
  }
}

export function downloadPdf(req: Request, res: Response): void {
  try {
    const { filename } = req.params;

    // Security: prevent path traversal
    const safeFilename = path.basename(filename);
    if (safeFilename !== filename) {
      res.status(400).json({ error: 'Невалідне ім\'я файлу' });
      return;
    }

    const buffer = readPdfFile(safeFilename);
    if (!buffer) {
      res.status(404).json({ error: 'PDF файл не знайдено' });
      return;
    }

    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `attachment; filename="${safeFilename}"`);
    res.send(buffer);
  } catch (error: any) {
    res.status(500).json({ error: 'Помилка завантаження PDF', details: error.message });
  }
}
