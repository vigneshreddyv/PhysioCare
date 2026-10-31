import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const isHomeVisitDemo = mode === 'home-visit-demo';

  return {
    plugins: [react()],
    server: {
      strictPort: isHomeVisitDemo,
      proxy: {
        '/api': {
          target: isHomeVisitDemo
            ? 'http://127.0.0.1:8002'
            : 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false,
        },
      },
    },
  };
});
