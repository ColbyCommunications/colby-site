/** @type {import('tailwindcss').Config} */
export default {
  purge: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"], // Add purge option for file paths
  theme: {
    extend: {
      colors: {
        colbyBlue: "#002169",
        deepYellow: "#EEB808",
        brightBlue: "#5d8EE5",
        blueBlack: "#1A2D38",
        drkBlueGrey: "#707682",
        ltBlueGrey: "#DCE4E2",
        warmRed: "#DD3C27",
      },
    },
    fontFamily: {
      sans: ["libre-franklin", "sans-serif"],
    },
    fontSize: {
      header: "1.85rem",
      xs: ".75rem",
      sm: ".875rem",
      base: "1rem",
      lg: "1.125rem",
      xl: "1.15rem",
      xl2: "1.2rem",
      "2xl": "1.25rem",
      "3xl": "1.35rem",
      "4xl": "1.65rem",
      "5xl": "2rem",
      "6xl": "3rem",
    },
    container: {
      center: true,
    },
    maxHeight: {
      0: "0",
      list: "50rem",
      "1/2": "50%",
      full: "100%",
    },
  },
  variants: {},
  plugins: [],
};
