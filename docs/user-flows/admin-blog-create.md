### FLOW: `admin-blog-create`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/blog/create`
- **Description:** Create a new bilingual blog post.
- **Steps:**
  1. Admin navigates to `/panel/blog/create`.
  2. Blog form renders with bilingual fieldsets (ES + EN: title, excerpt, content).
  3. Admin fills in both language versions.
  4. Admin optionally uploads a cover image.
  5. Admin submits the form.
  6. API call to `POST /api/blog/admin/create/`.
  7. On success, admin is redirected to blog list.
- **Branches:**
  - [Branch A — Validation error] Form shows errors, admin corrects and resubmits.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-blog-create.spec.js`

- **Formato editorial:** Los extractos y cuerpos de artículo admiten Visual y Fuente Markdown; las anotaciones de formato acompañan el contenido y el JSON estructurado mantiene su editor de código.
