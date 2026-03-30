import puppeteer from 'puppeteer-core';
import path from 'path';
import fs from 'fs';

const PDF_STORAGE_PATH = process.env.PDF_STORAGE_PATH || path.join(__dirname, '../../uploads/pdfs');

if (!fs.existsSync(PDF_STORAGE_PATH)) {
  fs.mkdirSync(PDF_STORAGE_PATH, { recursive: true });
}

function findChromiumExecutable(): string {
  const candidates = [
    process.env.PUPPETEER_EXECUTABLE_PATH,
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/local/bin/chromium',
    '/snap/bin/chromium',
    `${process.env.HOME || '/root'}/.cache/ms-playwright/chromium-1194/chrome-linux/chrome`,
  ].filter(Boolean) as string[];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new Error('Chromium not found. Set PUPPETEER_EXECUTABLE_PATH or install chromium.');
}

export async function htmlToPdf(html: string, filename: string): Promise<string> {
  const executablePath = findChromiumExecutable();
  const browser = await puppeteer.launch({
    executablePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
  try {
    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: 'networkidle0' });
    const pdfBuffer = await page.pdf({
      format: 'A4',
      printBackground: true,
      margin: { top: '15mm', bottom: '15mm', left: '15mm', right: '15mm' },
    });
    const filePath = path.join(PDF_STORAGE_PATH, filename);
    fs.writeFileSync(filePath, pdfBuffer);
    return filePath;
  } finally {
    await browser.close();
  }
}

export function getPdfUrl(filename: string): string {
  return `/api/documents/pdf/${filename}`;
}

export function readPdfFile(filename: string): Buffer | null {
  const filePath = path.join(PDF_STORAGE_PATH, filename);
  if (!fs.existsSync(filePath)) return null;
  return fs.readFileSync(filePath);
}
