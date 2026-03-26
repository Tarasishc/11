import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

const DB_PATH = process.env.DATABASE_URL || path.join(__dirname, '../../data/app.db');

// Ensure data directory exists
const dataDir = path.dirname(DB_PATH);
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

let db: Database.Database;

export function getDb(): Database.Database {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
    initializeSchema(db);
  }
  return db;
}

function initializeSchema(db: Database.Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS contacts (
      id TEXT PRIMARY KEY,
      type TEXT NOT NULL CHECK(type IN ('Постачальник', 'Покупець')),
      fullName TEXT NOT NULL,
      inn TEXT DEFAULT '',
      edrpou TEXT DEFAULT '',
      iban TEXT DEFAULT '',
      bank TEXT DEFAULT '',
      address TEXT DEFAULT '',
      phone TEXT DEFAULT '',
      email TEXT DEFAULT '',
      grp TEXT DEFAULT '',
      additionalCode TEXT DEFAULT '',
      createdAt TEXT NOT NULL,
      updatedAt TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS documents (
      id TEXT PRIMARY KEY,
      number TEXT NOT NULL,
      type TEXT NOT NULL CHECK(type IN ('Акт', 'Рахунок')),
      date TEXT NOT NULL,
      client TEXT NOT NULL,
      seller TEXT NOT NULL,
      amount REAL NOT NULL DEFAULT 0,
      pdfUrl TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'generated',
      createdAt TEXT NOT NULL
    );
  `);
}

export default getDb;
