import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
  // JSON import edildiğinde (scripts/data/...) üst dizinlere erişebilsin
  // diye Vite'ın fs kısıtını proje köküne açıyoruz.
  // Not: Alternatif olarak public/ içine veya src/data'ya taşıyabilirsiniz.
  resolve: {
    preserveSymlinks: true,
  },
});
