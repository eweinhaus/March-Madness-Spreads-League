import axios from "axios";
import { auth } from "./firebase";

const isDev = import.meta.env.MODE === "development";
const raw = import.meta.env.VITE_API_URL;
const API_URL =
  (typeof raw === "string" && raw.trim() !== "" ? raw.trim().replace(/\/$/, "") : "") ||
  (isDev ? "http://localhost:8000" : "");

if (!API_URL) {
  throw new Error(
    "VITE_API_URL must be set for production builds. Point it at your backend base URL (no trailing slash), e.g. https://your-api.vercel.app"
  );
}

const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use(
  async (config) => {
    const user = auth.currentUser;
    if (!user) {
      return config;
    }
    try {
      const token = await user.getIdToken();
      config.headers = config.headers ?? {};
      config.headers.Authorization = `Bearer ${token}`;
      return config;
    } catch (err) {
      return Promise.reject(err);
    }
  },
  (error) => Promise.reject(error)
);

export { API_URL };
export default api;
