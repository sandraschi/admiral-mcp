/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: { 50: "#fffbeb", 500: "#f59e0b", 600: "#d97706" },
      },
    },
  },
  plugins: [],
};
