import puppeteer from 'puppeteer-core';
import path from 'path';
import fs from 'fs';

const PDF_STORAGE_PATH = process.env.PDF_STORAGE_PATH || path.join(__dirname, '../../uploads/pdfs');

// Ensure PDF storage directory exists
if (!fs.existsSync(PDF_STORAGE_PATH)) {
  fs.mkdirSync(PDF_STORAGE_PATH, { recursive: true });
}

/**
 * Convert HTML content to PDF file and return the file path
 */
// Detect system Chromium/Chrome executable
function findChromiumExecutable(): string {
  const candidates = [
    process.env.PUPPETEER_EXECUTABLE_PATH,
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/local/bin/chromium',
    '/snap/bin/chromium',
    // Playwright bundled Chromium (common in CI/dev environments)
    `${process.env.HOME || '/root'}/.cache/ms-playwright/chromium-1194/chrome-linux/chrome`,
    `${process.env.HOME || '/root'}/.cache/ms-playwright/chromium-1161/chrome-linux/chrome`,
    `${process.env.HOME || '/root'}/.cache/ms-playwright/chromium-1112/chrome-linux/chrome`,
  ].filter(Boolean) as string[];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new Error(
    'Chromium not found. Install it with: apt-get install chromium  OR  set PUPPETEER_EXECUTABLE_PATH env var'
  );
}

export async function htmlToPdf(html: string, filename: string): Promise<string> {
  const executablePath = findChromiumExecutable();

  const browser = await puppeteer.launch({
    executablePath,
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
  });

  try {
    const page = await browser.newPage();

    // Set content with Ukrainian font support
    await page.setContent(html, { waitUntil: 'networkidle0' });

    // Generate PDF
    const pdfBuffer = await page.pdf({
      format: 'A4',
      printBackground: true,
      margin: {
        top: '15mm',
        bottom: '15mm',
        left: '15mm',
        right: '15mm',
      },
    });

    const filePath = path.join(PDF_STORAGE_PATH, filename);
    fs.writeFileSync(filePath, pdfBuffer);

    return filePath;
  } finally {
    await browser.close();
  }
}

/**
 * Get the public URL for a PDF file
 */
export function getPdfUrl(filename: string): string {
  return `/api/documents/pdf/${filename}`;
}

/**
 * Read a PDF file buffer for streaming
 */
export function readPdfFile(filename: string): Buffer | null {
  const filePath = path.join(PDF_STORAGE_PATH, filename);
  if (!fs.existsSync(filePath)) return null;
  return fs.readFileSync(filePath);
}

/**
 * Check if a PDF file exists
 */
export function pdfExists(filename: string): boolean {
  return fs.existsSync(path.join(PDF_STORAGE_PATH, filename));
}
