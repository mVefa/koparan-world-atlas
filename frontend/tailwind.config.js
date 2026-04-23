/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        neon: {
          orange: '#ff7a1a',
          orangeGlow: '#ffb36b',
        },
        space: {
          900: '#05070d',
          800: '#0a0f1f',
          700: '#111728',
          600: '#1a2238',
        },
      },
      boxShadow: {
        'neon-orange':
          '0 0 12px rgba(255,122,26,0.65), 0 0 40px rgba(255,122,26,0.35)',
      },
      fontFamily: {
        display: ['Inter', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { opacity: '0.7' },
          '50%': { opacity: '1' },
        },
      },
      animation: {
        pulseGlow: 'pulseGlow 2.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
