import { Router } from 'express';
import * as contactsController from '../controllers/contactsController';

const router = Router();

/**
 * @swagger
 * /api/contacts:
 *   get:
 *     summary: Get all contacts
 *     tags: [Contacts]
 *     parameters:
 *       - in: query
 *         name: type
 *         schema:
 *           type: string
 *           enum: [Постачальник, Покупець]
 *     responses:
 *       200:
 *         description: List of contacts
 */
router.get('/', contactsController.getContacts);

/**
 * @swagger
 * /api/contacts/{id}:
 *   get:
 *     summary: Get contact by ID
 *     tags: [Contacts]
 */
router.get('/:id', contactsController.getContact);

/**
 * @swagger
 * /api/contacts:
 *   post:
 *     summary: Create new contact
 *     tags: [Contacts]
 */
router.post('/', contactsController.createContact);

/**
 * @swagger
 * /api/contacts/{id}:
 *   put:
 *     summary: Update contact
 *     tags: [Contacts]
 */
router.put('/:id', contactsController.updateContact);

/**
 * @swagger
 * /api/contacts/{id}:
 *   delete:
 *     summary: Delete contact
 *     tags: [Contacts]
 */
router.delete('/:id', contactsController.deleteContact);

export default router;
