const isDevelopment = import.meta.env.MODE === 'development';

export const API_URL = isDevelopment 
  ? 'http://localhost:8000'
  : 'https://march-madness-backend-qyw5.onrender.com'; 