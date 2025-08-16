const isDevelopment = import.meta.env.MODE === 'development';

export const API_URL = isDevelopment 
  ? 'http://192.168.4.38:8000'
  : 'https://march-madness-backend-qyw5.onrender.com'; 