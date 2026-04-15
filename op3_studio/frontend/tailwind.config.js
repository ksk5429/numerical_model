/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        op3: {
          bg: "#0d1117",
          panel: "#161b22",
          accent: "#58a6ff",
          warn: "#e3b341",
          danger: "#ff7b72",
          ok: "#3fb950",
        },
      },
    },
  },
  plugins: [],
};
