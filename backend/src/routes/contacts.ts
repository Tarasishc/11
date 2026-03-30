import { Router } from 'express';
import * as c from '../controllers/contactsController';
const router = Router();
router.get('/', c.getContacts);
router.get('/:id', c.getContact);
router.post('/', c.createContact);
router.put('/:id', c.updateContact);
router.delete('/:id', c.deleteContact);
export default router;
