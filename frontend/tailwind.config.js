/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          900: '#0d0d0f',
          800: '#131316',
          700: '#1a1a1f',
          600: '#222228',
          500: '#2a2a32',
        },
        brand: {
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
        },
        accent: {
          400: '#34d399',
          500: '#10b981',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
