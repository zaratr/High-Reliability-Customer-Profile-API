# Distributed Edge API Service

## ?? 2026 Architecture Modernization
Modern high-performance APIs are moving away from centralized databases to **Edge Compute** models. This profile API has been migrated to use distributed SQLite for zero-latency data access.

### Key Features
1. **Distributed Edge DB:** Swapped legacy SQL Server for **libSQL/Turso**, replicating the database to edge nodes globally.
2. **WASM Compatibility:** Designed for near-instant cold starts by compiling to WebAssembly, allowing execution directly at the edge (e.g., Cloudflare Workers).
3. **High Reliability:** Ensures the profile service remains available and fast regardless of the user's geographic location.

## ??? Tech Stack
*   **Database:** libSQL / Turso (Distributed SQLite)
*   **Architecture:** Edge Compute, WASM-ready
*   **Backend:** Python
