import { Router } from 'express';
import * as d from '../controllers/documentsController';
const router = Router();
router.post('/generate', d.generateDocument);
router.get('/', d.getDocuments);
router.get('/pdf/:filename', d.downloadPdf);
router.get('/:id', d.getDocument);
export default router;
