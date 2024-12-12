import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 5173,
		proxy: {
			'/ws': {
				target: 'ws://127.0.0.1:3000',
				ws: true,
				changeOrigin: true,
				secure: false,
				rewrite: (path) => path
			}
		}
	}
});
