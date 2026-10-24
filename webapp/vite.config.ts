import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
	plugins: [react()],
	server: {
		host: "127.0.0.1",
		port: 11090,
		proxy: {
			"/api": "http://127.0.0.1:11089",
			"/health": "http://127.0.0.1:11089",
			"/mcp": "http://127.0.0.1:11089",
		},
	},
});
