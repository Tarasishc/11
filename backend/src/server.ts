import express from 'express';
import path from 'path';
import dotenv from 'dotenv';
import swaggerUi from 'swagger-ui-express';

import contactsRouter from './routes/contacts';
import documentsRouter from './routes/documents';

dotenv.config({ path: path.join(__dirname, '../.env') });

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

const swaggerDocument = {
  openapi: '3.0.0',
  info: {
    title: 'Financial PDF Generator API',
    version: '1.0.0',
    description: 'API для генерації фінансових документів',
  },
  servers: [{ url: `http://localhost:${PORT}` }],
  tags: [
    { name: 'Documents', description: 'Операції з документами' },
    { name: 'Contacts', description: 'Управління контактами' },
  ],
};

app.use('/api/docs', swaggerUi.serve, swaggerUi.setup(swaggerDocument));
app.use('/api/contacts', contactsRouter);
app.use('/api/documents', documentsRouter);

app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

const PUBLIC_DIR = path.join(__dirname, '../public');
app.use(express.static(PUBLIC_DIR));

app.get('*', (req, res) => {
  if (req.path.startsWith('/api/')) {
    res.status(404).json({ error: 'Not found' });
    return;
  }
  res.sendFile(path.join(PUBLIC_DIR, 'index.html'));
});

app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error('Unhandled error:', err);
  res.status(500).json({ error: 'Внутрішня помилка сервера', details: err.message });
});

app.listen(PORT, () => {
  console.log(`\n🌐 Сайт: http://localhost:${PORT}`);
  console.log(`📚 API docs: http://localhost:${PORT}/api/docs\n`);
});

export default app;
