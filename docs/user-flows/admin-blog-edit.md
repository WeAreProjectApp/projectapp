### FLOW: `admin-blog-edit`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/blog/:id/edit`
- **Description:** Edit an existing bilingual blog post.
- **Steps:**
  1. Admin navigates to `/panel/blog/:id/edit`.
  2. Blog post data loads from API (`GET /api/blog/admin/:id/detail/`).
  3. Edit form renders pre-filled with current bilingual data.
  4. Admin modifies content.
  5. Admin saves changes.
  6. API call to `PATCH /api/blog/admin/:id/update/`.
  7. Success feedback displays.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-blog-edit.spec.js`

- **Formato editorial:** Los extractos y cuerpos de artículo admiten Visual y Fuente Markdown; las anotaciones de formato se conservan al reabrir y en la lectura pública.
