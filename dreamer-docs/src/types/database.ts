export type CounterpartyType = 'buyer' | 'supplier'
export type DocumentType = 'invoice' | 'waybill' | 'contract'

export interface Profile {
  id: string
  full_name: string | null
  ipn: string | null
  address: string | null
  bank_name: string | null
  bank_account: string | null
  bank_mfo: string | null
  webhook_url: string | null
  terms_accepted_at: string | null
  created_at: string
  updated_at: string
}

export interface Counterparty {
  id: string
  user_id: string
  type: CounterpartyType
  name: string
  tax_id: string | null
  address: string | null
  bank_name: string | null
  bank_account: string | null
  bank_mfo: string | null
  created_at: string
}

export interface DocumentHistoryRow {
  id: string
  user_id: string
  counterparty_id: string | null
  counterparty_name: string
  document_type: DocumentType
  total_amount: number
  google_doc_url: string
  created_at: string
}

export interface DocumentItem {
  name: string
  quantity: number
  unit: string
  price: number
  sum: number
}

export function isProfileComplete(profile: Profile | null): boolean {
  if (!profile) return false
  return !!(profile.full_name && profile.ipn && profile.address && profile.bank_account)
}
