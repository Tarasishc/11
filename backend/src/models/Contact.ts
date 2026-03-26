import { v4 as uuidv4 } from 'uuid';
import getDb from '../services/database';
import { Contact } from '../types';

export function getAllContacts(): Contact[] {
  const db = getDb();
  const rows = db.prepare('SELECT * FROM contacts ORDER BY fullName').all() as any[];
  return rows.map(mapRow);
}

export function getContactsByType(type: string): Contact[] {
  const db = getDb();
  const rows = db.prepare('SELECT * FROM contacts WHERE type = ? ORDER BY fullName').all(type) as any[];
  return rows.map(mapRow);
}

export function getContactById(id: string): Contact | null {
  const db = getDb();
  const row = db.prepare('SELECT * FROM contacts WHERE id = ?').get(id) as any;
  return row ? mapRow(row) : null;
}

export function findContactByNameAndType(fullName: string, type: string): Contact | null {
  const db = getDb();
  const row = db
    .prepare('SELECT * FROM contacts WHERE type = ? AND fullName LIKE ? LIMIT 1')
    .get(type, `%${fullName}%`) as any;
  return row ? mapRow(row) : null;
}

export function createContact(data: Omit<Contact, 'id' | 'createdAt' | 'updatedAt'>): Contact {
  const db = getDb();
  const now = new Date().toISOString();
  const id = uuidv4();

  db.prepare(`
    INSERT INTO contacts (id, type, fullName, inn, edrpou, iban, bank, address, phone, email, grp, additionalCode, createdAt, updatedAt)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    id, data.type, data.fullName, data.inn || '', data.edrpou || '',
    data.iban || '', data.bank || '', data.address || '',
    data.phone || '', data.email || '', data.group || '', data.additionalCode || '',
    now, now
  );

  return getContactById(id)!;
}

export function updateContact(id: string, data: Partial<Omit<Contact, 'id' | 'createdAt'>>): Contact | null {
  const db = getDb();
  const existing = getContactById(id);
  if (!existing) return null;

  const now = new Date().toISOString();
  db.prepare(`
    UPDATE contacts SET
      type = ?, fullName = ?, inn = ?, edrpou = ?, iban = ?, bank = ?,
      address = ?, phone = ?, email = ?, grp = ?, additionalCode = ?, updatedAt = ?
    WHERE id = ?
  `).run(
    data.type ?? existing.type,
    data.fullName ?? existing.fullName,
    data.inn ?? existing.inn,
    data.edrpou ?? existing.edrpou,
    data.iban ?? existing.iban,
    data.bank ?? existing.bank,
    data.address ?? existing.address,
    data.phone ?? existing.phone,
    data.email ?? existing.email,
    data.group ?? existing.group,
    data.additionalCode ?? existing.additionalCode,
    now,
    id
  );

  return getContactById(id);
}

export function deleteContact(id: string): boolean {
  const db = getDb();
  const result = db.prepare('DELETE FROM contacts WHERE id = ?').run(id);
  return result.changes > 0;
}

function mapRow(row: any): Contact {
  return {
    id: row.id,
    type: row.type,
    fullName: row.fullName,
    inn: row.inn,
    edrpou: row.edrpou,
    iban: row.iban,
    bank: row.bank,
    address: row.address,
    phone: row.phone,
    email: row.email,
    group: row.grp,
    additionalCode: row.additionalCode,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
  };
}
