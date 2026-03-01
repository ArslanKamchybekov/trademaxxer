import { createRoot } from "react-dom/client"
import App from "./App.jsx"
import "reveal.js/dist/reveal.css"
import "reveal.js/dist/theme/black.css"
import "./index.css"

createRoot(document.getElementById("root")).render(<App />)
