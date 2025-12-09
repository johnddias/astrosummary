// API configuration - uses environment variable or defaults to localhost
export const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

// Debug logging to help diagnose API URL issues
console.log('=== API Configuration Debug ===');
console.log('VITE_API_URL env var:', import.meta.env.VITE_API_URL);
console.log('Final API_URL:', API_URL);
console.log('All env vars:', import.meta.env);
console.log('==============================');



