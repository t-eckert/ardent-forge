import type { Preview } from '@storybook/sveltekit';
import '../src/app.css';

const preview: Preview = {
	parameters: {
		backgrounds: {
			default: 'paper',
			values: [
				{ name: 'paper', value: '#FAF7F1' },
				{ name: 'bench', value: '#F1ECE0' },
				{ name: 'ink', value: '#1A1714' }
			]
		},
		controls: {
			matchers: {
				color: /(background|color)$/i,
				date: /Date$/i
			}
		},
		a11y: {
			test: 'todo'
		}
	}
};

export default preview;
