import { PurchasesPayload, type PurchasesPayload as PurchasesPayloadT } from '$lib/schemas/widgets/purchases';

export function makePurchases(overrides: Partial<PurchasesPayloadT> = {}): PurchasesPayloadT {
	return PurchasesPayload.parse({
		tool: 'finance.purchases',
		rangeLabel: 'Mon 06 → Sat 12 April',
		totalLabel: '$412.86',
		rows: [
			{ dateLabel: 'Fri 11', merchant: 'Loblaws', category: 'Groceries', amountLabel: '$142.18' },
			{ dateLabel: 'Thu 10', merchant: 'Canada Computers', category: 'Hardware', amountLabel: '$189.00' },
			{ dateLabel: 'Wed 09', merchant: 'Bridgehead Coffee', category: 'Cafés', amountLabel: '$12.40' },
			{ dateLabel: 'Mon 07', merchant: 'Anthropic', category: 'Software', amountLabel: '$69.28' }
		],
		...overrides
	});
}
