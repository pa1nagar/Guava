/**
 * Tailwind build config. css/tailwind.css is COMMITTED because Netlify publishes
 * the repo root with no build step. Regenerate it after any class change in
 * *.html or js/*.js:
 *
 *   npx -y tailwindcss@3.4.17 -c tailwind.config.js -i css/tailwind.input.css -o css/tailwind.css --minify
 *
 * (Do not add a package.json at the repo root: Netlify would try to install it.)
 * brand.muted is #6B7280 on most pages; sell-smart.html used #4B5563 (higher
 * contrast), which is now the single value for every page.
 */
module.exports = {
  content: ['./*.html', './js/**/*.js'],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: '#FDFBF7',
          primary: '#1E3A2B',
          secondary: '#4A7C59',
          accent: '#E07A5F',
          dark: '#2B2D42',
          muted: '#4B5563',
        },
      },
      // Small text floor: text-xs = 14px, text-sm = 16px (raises every existing
      // small-text class without editing each page).
      fontSize: {
        xs: ['0.875rem', { lineHeight: '1.25rem' }],
        sm: ['1rem', { lineHeight: '1.5rem' }],
      },
      fontFamily: {
        sans: ['system-ui', 'Noto Sans Devanagari', 'Mukta', 'Nirmala UI', 'Mangal', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
};