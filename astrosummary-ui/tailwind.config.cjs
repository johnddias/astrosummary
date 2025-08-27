/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          main: '#111827',
          sidebar: '#1F2937',
          card: '#0F172A',
        },
        text: {
          primary: '#F9FAFB',
          secondary: '#9CA3AF',
        },
        accent: {
          primary: '#14B8A6',
          secondary: '#6366F1',
        },
        need: '#374151',
      },
      borderRadius: {
        xl: '12px',
      },
    },
  },
  plugins: [],
};
