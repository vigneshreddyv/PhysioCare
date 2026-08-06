## CORS Issue Resolved

I've configured a proxy in the Vite development server to forward API requests to your backend, which should resolve the CORS error.

### Changes Made:
1. Updated `vite.config.js` to include a proxy for `/api` requests:
   ```javascript
   server: {
     proxy: {
       '/api': {
         target: 'http://localhost:8000',
         changeOrigin: true,
         secure: false,
       }
     }
   }
   ```

### How It Works:
- When your frontend makes a request to `/api/auth/login` (or any path starting with `/api`),
- Vite's development server will proxy that request to `http://localhost:8000/api/auth/login`
- This avoids the CORS issue because the browser sees the request as same-origin (to `localhost:5173` or whatever port Vite is using)
- The `changeOrigin: true` option ensures the Host header is set correctly for the backend

### Next Steps:
1. **Restart your development server** (if it's currently running) to apply the proxy configuration
2. The Vite dev server should now proxy API requests to your backend running on port 8000
3. Your login request (and other API calls) should no longer encounter CORS errors

### Note:
- Make sure your backend is actually running on `http://localhost:8000`
- If your backend runs on a different port or host, update the `target` in the proxy configuration accordingly
- This configuration is for development only. In production, you'll need to configure CORS properly on your backend or use a reverse proxy (like Nginx) to serve both frontend and backend from the same origin

The original request to fix the you can be resolved with this proxy setup during development.