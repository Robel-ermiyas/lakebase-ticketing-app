# Support Ticketing System (Lakebase + Databricks Apps)

A small Streamlit app for creating support tickets and threaded messages,
backed entirely by Lakebase (managed Postgres on Databricks).

## Stack
- **UI:** Streamlit
- **Database:** Lakebase Postgres (Autoscaling)
- **Hosting:** Databricks Apps
- **Auth to DB:** OAuth token rotation via the app's service principal (no passwords stored)

## Files
- `app.py` — the Streamlit app (list/create/update tickets, add messages)
- `requirements.txt` — Python dependencies
- `app.yaml` — Databricks App runtime config (start command + Lakebase connection env vars)
- `schema.sql` — table definitions, sample data, and service-principal grants

## Local development
```bash
databricks auth login
export PGHOST="<your-endpoint-hostname>"
export PGDATABASE="databricks_postgres"
export PGUSER="your.email@example.com"   # your own identity for local testing
export PGPORT="5432"
export PGSSLMODE="require"
export ENDPOINT_NAME="projects/<project-id>/branches/<branch-id>/endpoints/<endpoint-id>"

pip install -r requirements.txt
streamlit run app.py
```

## Deployment
Short version:
1. Create a Lakebase Autoscaling project.
2. Run `schema.sql` (tables + sample data) in the Lakebase SQL Editor.
3. Create a Databricks App, connect this repo as its source (Git folder).
4. Copy the app's `DATABRICKS_CLIENT_ID`, fill it into `app.yaml` and the
   grants section of `schema.sql`, and re-run those grants.
5. Deploy the app from the Apps UI.

## Reflection
- **Most difficult part:** What was the most difficult part?
The trickiest part wasn't the app code itself but the deployment plumbing — I hit a Databricks Free Edition compute-provisioning bug that blocked app creation entirely, then had to work through securely connecting to Lakebase using OAuth token rotation and Databricks Secrets instead of hardcoded credentials, and finally tracked down a silent GRANT failure where my app's service principal had a Postgres role but no actual table permissions, which took some SQL diagnostics to catch.

- **How Lakebase differs from a traditional analytics table:**
Lakebase is a full OLTP Postgres database built for fast, transactional, row-level reads and writes with ACID guarantees, which is exactly what an interactive app doing frequent single-record inserts and updates needs; a traditional analytics table (like a Delta table in Unity Catalog) is instead optimized for large batch scans and aggregations, not for the kind of constant small read/write traffic a live support ticketing app generates.

- **Feature to add next:**
I'd add AI-powered ticket triage — automatically suggesting a priority and category when a ticket is created, and maybe drafting a first response based on similar past tickets.
