/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class', 'html.theme-night'],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: '#050810',
        ink: '#eef1fa',
        mute: '#9aa3bd',
        gold: '#e8c36a',
        gold2: '#ffe3a1',
        ember: '#ff6b3d',
        ice: '#6fb3ff',
      },
      fontFamily: {
        cinzel: ['Cinzel', 'serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
