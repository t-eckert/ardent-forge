import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind class lists with proper conflict resolution.
 * Usage: `class={cn('p-4', condition && 'bg-ember', props.class)}`
 */
export function cn(...inputs: ClassValue[]): string {
	return twMerge(clsx(inputs));
}
