# Using your own photos

1. Put JPEG files of at least 1600 px width in `images/src/own/` (create the folder; it is git-ignored with the rest of `images/src/`):
   - `hero-own.jpg` (home page hero and Taiwan Pink card)
   - `orchard-own.jpg` (banners and empty states)
   - `farmer-own.jpg` (sign-in and onboarding banner)
   - `market-own.jpg` (price section, optional)
2. From the repo root run: `python tools/images/build_images.py --own`
   (needs Pillow: `pip install pillow`). Files that exist in `images/src/own/` win over the stock originals; the rest keep the stock photo.
3. The script writes the same output names (`images/hero-480.webp`, `hero-960.webp`, `hero-480.jpg`, and so on), so no HTML change is needed.
4. Commit the new files in `images/`. Replace the matching row in `images/CREDITS.md` and the entry in `privacy.html` (`privacy.credits.*` keys in `js/i18n-public.js`) with "Own photo".
5. Bump `STATIC` in `sw.js` (for example `sf-static-v3`) so returning visitors get the new hero.

Only use photos you took yourself or have the right to publish. Do not use AI-generated pictures.
