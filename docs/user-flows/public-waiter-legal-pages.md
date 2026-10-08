### FLOW: `public-waiter-legal-pages`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Routes:** `/waiter`, `/waiter/privacy`, `/waiter/terms`, `/waiter/data-deletion` (short aliases `/privacidad`, `/terminos`, `/eliminacion-de-datos` 301 to the es-co pages)
- **Description:** Open the public Waiter product page and reach its privacy policy, terms of service and data deletion instructions (the URLs registered in the Meta app review), each showing the verified legal identity in the legal footer.
- **Steps:**
  1. Guest opens `/es-co/waiter` and sees the product, the four WhatsApp connection steps and the data ownership block.
  2. Guest follows the legal footer links to the privacy policy, the terms of service and the data deletion instructions.
  3. Each legal page renders its title, sections and the legal footer with the trade name, NIT, address, phone and email.
  4. On `/en-us/...` the same pages render the courtesy English translation with a notice that the Spanish text prevails.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/public/public-waiter-legal-pages.spec.js`
