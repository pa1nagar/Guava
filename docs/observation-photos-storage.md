# Observation photos: storage bucket (owner step)

The backend now uploads each cleaned observation photo (GPS metadata removed) to a private
Supabase Storage bucket and lists photos on `GET /api/farmers/me/observations` with one-hour signed links.

Until the bucket exists, saving a photo still works (the database row is saved) but the bytes are not
stored and the thumbnail shows "Photo not available". Nothing breaks.

## What you need to do once

1. Supabase dashboard, **Storage**, **New bucket**.
2. Name: `observation-photos` (or set `OBSERVATION_PHOTO_BUCKET` on Render to another name).
3. Leave **Public bucket** switched **off**. Do not add any public policy. The backend uses the
   service key to create signed links, so no extra policy is needed.
4. Photos uploaded before the bucket existed have no stored file. Upload them again if needed.

No SQL is required.
