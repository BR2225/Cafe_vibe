# Café Vibe: every table is a taste sensor

A QR code on every café table opens a lightweight web page. Customers pick a mood (Working / Meeting / Unwinding), react to a few AI-picked items (❤️ 😐 ✕), or judge the whole set:

- **I like this menu**: shows the full menu ranked around their taste
- **I sort of like it**: keeps the good ones and swaps the rest
- **Not for me**: shows a completely different set

Every tap is anonymous, labelled preference data the café never had before. The **owner dashboard** turns those taps into live demand insights ("Nachos shown 7×, rejected 2×, never ordered"), and Gemini writes concrete menu changes from them. A new café onboards by **photographing its paper menu**: Gemini extracts the items, prices, veg status, likely allergens and taste tags, and the owner reviews them before publishing.

## Google tech
| Piece | Used for |
|---|---|
| **Gemini** (`gemini-3.8-flash`, with fallbacks) | Menu photo → structured menu; owner insights |
| **Gemini Embeddings** (`gemini-embedding-001`) | Item taste vectors; mood-based cold start |
| **Cloud Run** | Hosts the app (one container) |
| **Cloud SQL for PostgreSQL** | Menu, visits, taps, orders |
| **Secret Manager** | Gemini key, DB password, staff PIN |
| **Cloud Build** | Builds from GitHub on every push |

## How recommendations work
- **Cold start:** the mood + time of day is embedded and matched against the menu, so the first set is already relevant.
- **Taps** nudge a per-visit taste vector (❤️ +1, 😐 +0.25, ✕ −0.7). Vectors are centred on the menu's mean, so they capture what makes items *different* (coffee vs tea, sweet vs savoury).
- **Variety:** sets are picked MMR-style, penalising near-duplicates.
- **No LLM call in the tap loop:** every tap is pure vector math and instant. Gemini is used only for onboarding and insights.

## Run locally
```bash
pip install -r requirements.txt
cp .env.example .env        # add your GEMINI_API_KEY
uvicorn app.main:app --reload --port 8080
```
- Customer page: http://localhost:8080/t/1
- Owner dashboard: http://localhost:8080/admin (PIN from `ADMIN_PIN`, default `1234`)

Locally it uses SQLite (`cafe.db`). On Cloud Run it uses Cloud SQL.

## Deploy: Cloud Run from GitHub + Cloud SQL

### 1. Cloud SQL (PostgreSQL, region `asia-south1`)
1. Under **Databases**, create `cafe`.
2. Under **Users**, add `cafe_app` with a password.
3. In **Cloud SQL Studio**, log in as `postgres` to database `cafe` and run:
   ```sql
   GRANT ALL ON SCHEMA public TO cafe_app;
   ```
4. Copy the **Connection name** (`PROJECT:asia-south1:INSTANCE`).

### 2. Secrets (Secret Manager)
Create `GEMINI_API_KEY`, `DB_PASS`, `ADMIN_PIN` and `SECRET_KEY` (any long random string).

### 3. Cloud Run service
1. Go to Cloud Run → **Deploy container** → **Service** → **Continuously deploy from a repository**.
2. Set up Cloud Build: connect GitHub, choose this repo and branch `^main$`, and pick **Dockerfile** as the build type.
3. Region `asia-south1`. Authentication: **Allow public access** (customers scan QR codes without logging in).
4. Under **Containers → Variables & secrets**:
   - Env vars: `INSTANCE_CONNECTION_NAME`, `DB_USER=cafe_app`, `DB_NAME=cafe`, optionally `CAFE_NAME`
   - Secrets as env vars: `GEMINI_API_KEY`, `DB_PASS`, `ADMIN_PIN`, `SECRET_KEY`
5. Under **Cloud SQL connections**, add the instance.
6. Give the service account (**Security** tab) the **Cloud SQL Client** and **Secret Manager Secret Accessor** roles.

After that, every push to `main` redeploys automatically.
