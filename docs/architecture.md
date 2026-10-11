# System Architecture — Aerial Crowd Intelligence

## 1. Overview
Aerial Crowd Intelligence is a modular web application for analyzing crowd spatial organization, closeness, and collective behavior from aerial photographs and drone video footage.

## 2. Logical Components

```
+---------------------------------------------------------------------------------------+
|                                    REACT FRONTEND                                     |
|  - React 18, TypeScript, Tailwind CSS, Lucide Icons, Canvas Overlay Visualizer       |
+-------------------------------------------+-------------------------------------------+
                                            | REST API / JSON / Multipart
                                            v
+---------------------------------------------------------------------------------------+
|                                    FASTAPI BACKEND                                    |
|  - Auth & Security: Salted Bcrypt, Signed JWT Tokens                                  |
|  - Session & Media Management: Validation, Resolution Inspection, Private Storage     |
|  - Job Orchestrator & Asynchronous Task Executor                                      |
|  - Export Service: Structured JSON & Memory-Streamed CSV                              |
+--------------------+-------------------------------------+----------------------------+
                     |                                     |
                     v                                     v
+-----------------------------+         +-----------------------------------------------+
|      PERSISTENCE LAYER      |         |             COMPUTER VISION ENGINE            |
|  - SQLite (Local Dev)       |         |  - Preprocessing: Resolution Scale & ROI Mask |
|    / PostgreSQL (Production)|         |  - Detection: Adaptive Aerial Blob Density    |
|  - SQLAlchemy 2.0 ORM       |         |  - Clustering: SciPy HAC (Ward / Complete)    |
|  - Alembic Migrations       |         |  - Closeness: KDTree 1-NN & Convex Hull Area  |
|  - Private Local Disk       |         |  - Motion: GMC RANSAC Affine & Polar Stats    |
|    Storage Adapter          |         |  - Formation: Dynamic Temporal Transition     |
+-----------------------------+         +-----------------------------------------------+
```

## 3. Component Details
- **Frontend**: A desktop-first, mobile-responsive single-page application built with React 18, TypeScript, and Tailwind CSS.
- **Backend API**: A FastAPI service providing Pydantic v2 validated endpoints under `/api/v1`.
- **Database**: Relational schema managed via SQLAlchemy 2.0 and Alembic.
- **Media Storage**: Private volume storage using UUIDv4 filenames and content-type validation.
- **Analytical Engine**: Modular Python algorithms using OpenCV, SciPy, and NumPy.
