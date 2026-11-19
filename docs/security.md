# Local workspace access and storage

The application has no registration, login, bearer tokens or per-user access control.
The dashboard and API expose a shared workspace on the local computer. Existing
sessions are listed regardless of their legacy owner. New sessions use an internal,
non-login bookkeeping owner so existing databases require no destructive migration.
Legacy accounts and password hashes remain in the database but are not exposed by
any profile, registration or login endpoint.

Vite, the native backend startup script and Docker published ports bind to loopback.
No public deployment is configured. Media paths are resolved within approved storage
roots, uploads are validated, and job/media session associations remain enforced.
Deletion still removes the requested session/media and associated artifacts.

The former /api/v1/auth endpoints are removed, including from OpenAPI. No signing
secret is required. Old browser tokens have no effect and the client no longer reads
or sends them. CORS does not allow credentialed requests.
