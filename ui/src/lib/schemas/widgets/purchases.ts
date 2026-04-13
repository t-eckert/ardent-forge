import { z } from 'zod';

/** finance.purchases — spending window with per-row detail. */
export const PurchaseRow = z.object({
	dateLabel: z.string(),
	merchant: z.string(),
	category: z.string(),
	amountLabel: z.string()
});

export const PurchasesPayload = z.object({
	tool: z.literal('finance.purchases'),
	rangeLabel: z.string(),
	totalLabel: z.string(),
	rows: z.array(PurchaseRow).min(1)
});

export type PurchaseRow = z.infer<typeof PurchaseRow>;
export type PurchasesPayload = z.infer<typeof PurchasesPayload>;
