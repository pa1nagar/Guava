# Knowledge admin: owner steps

The admin page is `admin.html` (open it by its address; it is not linked from the site menu). Nothing in it reaches farmers until an item is approved.
Replace every `<placeholder>` below with your own value. Do not commit real emails or keys.

1. **Create the tables.** Open the Supabase SQL editor and run `backend/migrations/2026-12-knowledge-admin.sql` once. It is safe to run again.
2. **Make yourself the first admin.** Choose one:
   - On Render, set the environment variable `ADMIN_BOOTSTRAP_EMAILS` to `<your-google-email>` (a comma list is allowed), redeploy, sign in once on the site with that Google account, then open `admin.html`. The first sign-in is promoted to admin only while there is no admin yet and only if the email is confirmed.
   - Or run the one-line SQL insert shown in the header comment of the migration file, with your own `auth.users` id in place of `<AUTH_USER_UUID>` and your email and name in place of `<ADMIN_EMAIL>` and `<DISPLAY_NAME>`.
3. **Add the agriculture expert as a reviewer.** In `admin.html` open the **Reviewers** tab, enter `<expert-email>`, a display name and a credential (for example post and institute). If the expert has not signed in yet, an invitation is saved and applies the first time they sign in with that email (valid 14 days). A reviewer with no credential cannot approve high-risk items.
4. **Import the draft items.** On the **Dashboard** choose **Preview import**, check the numbers, then **Import seed items**. All items arrive as drafts (184 in the bundled file). Importing again never overwrites an item that was edited or reviewed.
5. **The expert reviews.** The expert opens each item, checks the sources and quotes, then approves, rejects or requests changes. High-risk items (pesticides, doses) need a reviewer with a name and credential; an admin cannot approve them alone. Hindi text is machine translated and needs a native review. Approvals expire after 365 days and the item returns to review.

Notes
- Only admins can add, edit, retire, restore, import, export or manage reviewers. Reviewers can comment, approve, reject, request changes and propose edits.
- History (versions, approvals, comments, audit trail) cannot be changed or deleted, not even by an admin.
- Use **Retire** instead of deleting; a retired item can be restored by an admin with a reason.
