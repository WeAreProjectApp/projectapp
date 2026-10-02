### FLOW: `platform-project-access-detail`

- **Module:** platform
- **Roles:** platform-admin, platform-client
- **Priority:** P1
- **Routes:** `/platform/projects/:id/access`
- **API:** project access endpoints under `/api/accounts/projects/:id/access/`
- **Interaction:** An admin reaches Accesos through project navigation and uses the shared editor over JWT transport.
- **Display outcome:** The scoped project detail renders both environments and masked credentials.
- **Success outcome:** An explicit field save updates the response through the platform endpoint.
- **Error outcome:** A client remains on an empty limited access view and never receives the administrative editor.
- **Failure outcome:** An API load failure appears with a retry control.
- **Coverage:** `e2e/platform/platform-project-access-detail.spec.js` and the five responsive platform profiles.
