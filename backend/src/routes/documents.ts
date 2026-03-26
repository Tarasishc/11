import { Router } from 'express';
import * as documentsController from '../controllers/documentsController';

const router = Router();

/**
 * @swagger
 * /api/documents/generate:
 *   post:
 *     summary: Generate a financial document (Акт or Рахунок)
 *     tags: [Documents]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [type, items, client, seller, city]
 *             properties:
 *               type:
 *                 type: string
 *                 enum: [Акт, Рахунок]
 *               items:
 *                 type: array
 *                 items:
 *                   type: object
 *                   properties:
 *                     name: { type: string }
 *                     price: { type: number }
 *               client:
 *                 type: string
 *               seller:
 *                 type: string
 *               city:
 *                 type: string
 *               contract:
 *                 type: string
 *               unit:
 *                 type: string
 *               date:
 *                 type: string
 *     responses:
 *       200:
 *         description: Generated document info
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 pdf_url: { type: string }
 *                 document_id: { type: string }
 *                 number: { type: string }
 */
router.post('/generate', documentsController.generateDocument);

/**
 * @swagger
 * /api/documents:
 *   get:
 *     summary: Get all documents
 *     tags: [Documents]
 */
router.get('/', documentsController.getDocuments);

/**
 * @swagger
 * /api/documents/{id}:
 *   get:
 *     summary: Get document by ID
 *     tags: [Documents]
 */
router.get('/:id', documentsController.getDocument);

/**
 * @swagger
 * /api/documents/pdf/{filename}:
 *   get:
 *     summary: Download PDF file
 *     tags: [Documents]
 */
router.get('/pdf/:filename', documentsController.downloadPdf);

export default router;
