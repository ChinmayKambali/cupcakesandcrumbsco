# Backend

FastAPI service for Cupcakes & Crumbs Co. See the [root README](../README.md) for setup, environment variables and the API reference.

Quick start (from the repository root):

```bash
cp backend/.env.example backend/.env    # then fill in values
psql -U postgres -d cupcakes_db -f backend/schema.sql
uvicorn backend.main:app --reload
```
