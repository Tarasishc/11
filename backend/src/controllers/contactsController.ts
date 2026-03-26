import { Request, Response } from 'express';
import { z } from 'zod';
import * as ContactModel from '../models/Contact';

const contactSchema = z.object({
  type: z.enum(['Постачальник', 'Покупець']),
  fullName: z.string().min(2, 'ПІБ обов\'язкове'),
  inn: z.string().optional().default(''),
  edrpou: z.string().optional().default(''),
  iban: z.string().optional().default(''),
  bank: z.string().optional().default(''),
  address: z.string().optional().default(''),
  phone: z.string().optional().default(''),
  email: z.string().email('Невірний email').optional().or(z.literal('')).default(''),
  group: z.string().optional().default(''),
  additionalCode: z.string().optional().default(''),
});

export function getContacts(req: Request, res: Response): void {
  try {
    const { type } = req.query;
    let contacts;

    if (type && (type === 'Постачальник' || type === 'Покупець')) {
      contacts = ContactModel.getContactsByType(type as string);
    } else {
      contacts = ContactModel.getAllContacts();
    }

    res.json(contacts);
  } catch (error: any) {
    res.status(500).json({ error: 'Помилка отримання контактів', details: error.message });
  }
}

export function getContact(req: Request, res: Response): void {
  try {
    const contact = ContactModel.getContactById(req.params.id);
    if (!contact) {
      res.status(404).json({ error: 'Контакт не знайдено' });
      return;
    }
    res.json(contact);
  } catch (error: any) {
    res.status(500).json({ error: 'Помилка отримання контакту', details: error.message });
  }
}

export function createContact(req: Request, res: Response): void {
  try {
    const result = contactSchema.safeParse(req.body);
    if (!result.success) {
      res.status(400).json({ error: 'Невалідні дані', details: result.error.flatten() });
      return;
    }

    const contact = ContactModel.createContact(result.data);
    res.status(201).json(contact);
  } catch (error: any) {
    res.status(500).json({ error: 'Помилка створення контакту', details: error.message });
  }
}

export function updateContact(req: Request, res: Response): void {
  try {
    const result = contactSchema.partial().safeParse(req.body);
    if (!result.success) {
      res.status(400).json({ error: 'Невалідні дані', details: result.error.flatten() });
      return;
    }

    const contact = ContactModel.updateContact(req.params.id, result.data);
    if (!contact) {
      res.status(404).json({ error: 'Контакт не знайдено' });
      return;
    }
    res.json(contact);
  } catch (error: any) {
    res.status(500).json({ error: 'Помилка оновлення контакту', details: error.message });
  }
}

export function deleteContact(req: Request, res: Response): void {
  try {
    const deleted = ContactModel.deleteContact(req.params.id);
    if (!deleted) {
      res.status(404).json({ error: 'Контакт не знайдено' });
      return;
    }
    res.json({ success: true });
  } catch (error: any) {
    res.status(500).json({ error: 'Помилка видалення контакту', details: error.message });
  }
}
