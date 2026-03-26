import { v4 as uuidv4 } from 'uuid';
import getDb from '../services/database';
import { Document } from '../types';

export function getAllDocuments(): Document[] {
  const db = getDb();
  const rows = db.prepare('SELECT * FROM documents ORDER BY createdAt DESC').all() as any[];
  return rows.map(mapRow);
}

export function getDocumentById(id: string): Document | null {
  const db = getDb();
  const row = db.prepare('SELECT * FROM documents WHERE id = ?').get(id) as any;
  return row ? mapRow(row) : null;
}

export function createDocument(data: Omit<Document, 'id' | 'createdAt'>): Document {
  const db = getDb();
  const now = new Date().toISOString();
  const id = uuidv4();

  db.prepare(`
    INSERT INTO documents (id, number, type, date, client, seller, amount, pdfUrl, status, createdAt)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    id, data.number, data.type, data.date,
    data.client, data.seller, data.amount,
    data.pdfUrl, data.status, now
  );

  return getDocumentById(id)!;
}

export function searchDocuments(query: string): Document[] {
  const db = getDb();
  const like = `%${query}%`;
  const rows = db.prepare(`
    SELECT * FROM documents
    WHERE client LIKE ? OR seller LIKE ? OR number LIKE ? OR type LIKE ?
    ORDER BY createdAt DESC
  `).all(like, like, like, like) as any[];
  return rows.map(mapRow);
}

export function filterDocuments(type?: string, dateFrom?: string, dateTo?: string): Document[] {
  const db = getDb();
  let sql = 'SELECT * FROM documents WHERE 1=1';
  const params: any[] = [];

  if (type) {
    sql += ' AND type = ?';
    params.push(type);
  }
  if (dateFrom) {
    sql += ' AND date >= ?';
    params.push(dateFrom);
  }
  if (dateTo) {
    sql += ' AND date <= ?';
    params.push(dateTo);
  }

  sql += ' ORDER BY createdAt DESC';
  const rows = db.prepare(sql).all(...params) as any[];
  return rows.map(mapRow);
}

function mapRow(row: any): Document {
  return {
    id: row.id,
    number: row.number,
    type: row.type,
    date: row.date,
    client: row.client,
    seller: row.seller,
    amount: row.amount,
    pdfUrl: row.pdfUrl,
    status: row.status,
    createdAt: row.createdAt,
  };
}
