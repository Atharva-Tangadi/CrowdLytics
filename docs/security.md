# Security & Privacy Architecture

## 1. Privacy by Design
- **Crowd-Level Insights Only**: No facial recognition, individual tracking, demographic classification, or biometric profiling.
- **Aggregated Results**: Persistent database records contain cluster statistics, centroids, convex hull areas, and density measures.

## 2. Authentication & Authorization
- **Password Protection**: Passwords hashed using bcrypt.
- **Signed Tokens**: HMAC-SHA256 JWT tokens.
- **Strict Tenant Isolation**: All session, media, job, and result queries require user ownership matching the authenticated JWT token. Unauthorized requests yield `404 Not Found`.

## 3. Media Ingestion Security
- **Server-Side File Keys**: Uploads are saved under UUIDv4 keys in a non-executable directory.
- **Format Verification**: File contents and dimensions are validated via OpenCV decoding.
- **Directory Traversal Prevention**: Storage paths are resolved and validated against the storage root directory.

## 4. API & Infrastructure Security
- **SQL Injection Prevention**: Parameterized queries via SQLAlchemy 2.0 ORM.
- **Cross-Origin Resource Sharing (CORS)**: Restricted to configured domains in production.
- **Secret Management**: Environment variables used for credentials; `.env.example` contains only non-sensitive placeholders.
