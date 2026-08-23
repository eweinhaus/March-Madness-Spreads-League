import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import 'bootstrap/dist/css/bootstrap.min.css';
import { SportConfigProvider } from './sportConfig';

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <SportConfigProvider>
      <App />
    </SportConfigProvider>
  </React.StrictMode>
);
