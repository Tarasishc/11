import { Request, Response } from 'express';
import { z } from 'zod';
import path from 'path';
import * as DocumentModel from '../models/Document';
import * as ContactModel from '../models/Contact';
import { generateDocumentHtml, generateDocumentHtmlLocal } from '../services/openaiService';
import { htmlToPdf, getPdfUrl, readPdfFile } from '../services/pdfGenerator';

const generateDocumentSchema = z.object({
  type: z.enum(['Акт', 'Рахунок']),
  items: z.array(z.object({ name: z.string().min(1), price: z.number().positive() })).min(1),
  client: z.string().min(1),
  seller: z.string().min(1),
  city: z.string().min(1),
  contract: z.string().optional().default('усний'),
  unit: z.string().optional().default('послуга'),
  date: z.string().optional(),
});

function generateDocumentNumber(): string {
  return Math.floor(Math.random() * 9000000000 + 1000000000).toString();
}

function formatDate(dateStr?: string): string {
  const d = dateStr ? new Date(dateStr) : new Date();
  return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()}`;
}

export async function generateDocument(req: Request, res: Response): Promise<void> {
  try {
    const result = generateDocumentSchema.safeParse(req.body);
    if (!result.success) { res.status(400).json({ error: 'Невалідні дані', details: result.error.flatten() }); return; }

    const { type, items, client, seller, city, contract, unit, date } = result.data;
    const sellerContact = ContactModel.findContactByNameAndType(seller, 'Постачальник');
    const clientContact = ContactModel.findContactByNameAndType(client, 'Покупець');
    const totalAmount = items.reduce((sum, item) => sum + item.price, 0);
    const documentNumber = generateDocumentNumber();
    const formattedDate = formatDate(date);

    const params = { type, items, client: clientContact, seller: sellerContact, city, contract: contract||'усний', unit: unit||'послуга', date: formattedDate, documentNumber, totalAmount };

    let html: string;
    if (process.env.OPENAI_API_KEY && process.env.OPENAI_API_KEY !== 'your_openai_api_key_here') {
      try { html = await generateDocumentHtml(params); }
      catch (e: any) { console.warn('OpenAI failed, using local template:', e.message); html = generateDocumentHtmlLocal(params); }
    } else {
      html = generateDocumentHtmlLocal(params);
    }

    const filename = `${type==='Акт'?'act':'invoice'}_${documentNumber}_${Date.now()}.pdf`;
    await htmlToPdf(html, filename);
    const pdfUrl = getPdfUrl(filename);

    const document = DocumentModel.createDocument({ number: documentNumber, type, date: formattedDate, client: clientContact?.fullName||client, seller: sellerContact?.fullName||seller, amount: totalAmount, pdfUrl, status: 'generated' });
    res.json({ pdf_url: pdfUrl, document_id: document.id, number: documentNumber });
  } catch (e: any) {
    console.error('Document generation error:', e);
    res.status(500).json({ error: 'Помилка генерації документа', details: e.message });
  }
}

export function getDocuments(req: Request, res: Response): void {
  try {
    const { search, type, dateFrom, dateTo } = req.query;
    let documents;
    if (search) documents = DocumentModel.searchDocuments(search as string);
    else if (type||dateFrom||dateTo) documents = DocumentModel.filterDocuments(type as string|undefined, dateFrom as string|undefined, dateTo as string|undefined);
    else documents = DocumentModel.getAllDocuments();
    res.json(documents);
  } catch (e: any) { res.status(500).json({ error: e.message }); }
}

export function getDocument(req: Request, res: Response): void {
  try {
    const document = DocumentModel.getDocumentById(req.params.id);
    if (!document) { res.status(404).json({ error: 'Документ не знайдено' }); return; }
    res.json(document);
  } catch (e: any) { res.status(500).json({ error: e.message }); }
}

export function downloadPdf(req: Request, res: Response): void {
  try {
    const safeFilename = path.basename(req.params.filename);
    const buffer = readPdfFile(safeFilename);
    if (!buffer) { res.status(404).json({ error: 'PDF файл не знайдено' }); return; }
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `attachment; filename="${safeFilename}"`);
    res.send(buffer);
  } catch (e: any) { res.status(500).json({ error: e.message }); }
}
