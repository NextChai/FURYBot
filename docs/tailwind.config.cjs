/** @type {import('tailwindcss').Config} */

module.exports = {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  mode: "jit",
  theme: {
    extend: {
      colors: {
        primary: "#00040f",
        dimWhite: "rgba(255, 255, 255, 0.7)",
        fury: "#4EDBFC",
        "primary-text-light": "#4edbfc",
        "primary-text-medium": "#2e9fb5",
        "primary-text-dark": "#1e5661",
        "gray-light": "#9090a7",
        "gray-medium": "#555870",
        "gray-dark": "#28293d",
        "white-light": "#fafafc",
        "white-medium": "#f2f2f4",
        "white-dark": "#ebeaef",
        "discord-gray": "#36393F"
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