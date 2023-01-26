/** @type {import('tailwindcss').Config} */

const colors = require('tailwindcss/colors')

module.exports = {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  mode: "jit",
  theme: {
    extend: {
      colors: {
        primary: "#00040f",
        dimWhite: "rgba(255, 255, 255, 0.7)",
        light: {
          text: "#1a1a1a",
          text_hover: "#525252",
          bg: "#f5f5f5",
          ws_bg: "#f5f5f5"
        },
        dark: {
          text: "#e5e5e5",
          bg: "#262626",
          text_hover: "#f5f5f5",
          ws_bg: "#121212"
        }
      },
      fontFamily: {
        poppins: ["Poppins", "sans-serif"],
      },
    },
    screens: {
      xs: "480px",
      ss: "620px",
      sm: "768px",
      md: "1060px",
      lg: "1200px",
      xl: "1700px",
    },
  },
  plugins: [],
};