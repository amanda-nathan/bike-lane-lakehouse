# Public MCP server on Google Cloud Run

People you give the access key to can connect an AI client (Claude, for example) to this server and ask about the data. Their client pays for its own questions; this server only runs the queries.

## Why Cloud Run

The first plan was a free Hugging Face Space (`space/`). Hugging Face now only runs Docker Spaces on free hardware for PRO subscribers, so the deploy failed with 402 Payment Required. Cloud Run runs the same container, has a free monthly allowance, and scales to zero when nobody is using it.

## What runs

One container, built from `space/Dockerfile`:

- **Trino**, with a single catalog: the mart tables on Cloudflare R2, read through a **read-only key**. The image's sample catalogs are removed, so nothing can be written anywhere.
- **The MCP server** on port 7860, with the same tools and limits as locally: one SELECT at a time on `iceberg.marts`, 30 seconds, 1,000 rows. It only accepts requests addressed to its own hostnames.
- **An access key.** Every request needs `Authorization: Bearer <MCP_ACCESS_KEY>`. Without it the server answers 401 before any tool or Trino runs, so a bot that finds the URL can't run up a bill.

The catalog URI, warehouse name, and endpoint are plain settings. The read-only R2 key and the access key are credentials, kept in Google Secret Manager, not in the image or the repo.

## Deploying

1. Install the Google Cloud CLI: `brew install --cask gcloud-cli`.
2. Sign in:
   ```bash
   gcloud auth login
   ```
   This opens a browser window to sign in to your Google account and saves a credential on this machine, so later `gcloud` commands act as you. It doesn't create or change anything in Google Cloud.
3. Find your billing account ID: `gcloud billing accounts list`. Cloud Run needs a billing account even when usage stays in the free tier.
4. Deploy:
   ```bash
   cloudrun/deploy.sh <billing-account-id>
   ```
   The script creates the `bike-lane-lakehouse` project, links billing, turns on the services it needs, stores the credentials in Secret Manager, builds the image in Cloud Build (Cloud Run needs an amd64 image; Macs build arm64), and deploys. It prints the MCP endpoint at the end. Running it again redeploys.
5. Set a budget alert in the Google Cloud console (Billing > Budgets & alerts), for example $5, so you get an email if anything starts costing money.

To connect from Claude Code, with the key from `.env`:

```bash
claude mcp add --transport http bikelake https://<service-url>/mcp \
  --header "Authorization: Bearer <MCP_ACCESS_KEY>"
```

To give someone access, send them the URL and the key. To shut everyone out, change `MCP_ACCESS_KEY` in `.env` and re-run `cloudrun/deploy.sh`.

## Settings and cost

| Setting | Value | Why |
|---|---|---|
| Region | `us-east1` | Close to Boston and New York; a lower-cost region |
| CPU / memory | 2 vCPU / 4 GiB | Enough for Trino on these tables; Trino's heap is half the memory |
| Instances | 0 to 1 | Scales to zero when idle; never more than one copy running |
| Startup CPU boost | on | Trino starts faster |

At the time of writing, Cloud Run's free tier covers 180,000 vCPU-seconds, 360,000 GiB-seconds, and 2 million requests a month, and an instance is billed only while it handles requests. With 4 GiB, the memory allowance is the limit: about 25 hours of active use a month. Image storage beyond Artifact Registry's free 0.5 GB costs a few cents a month. Check [Cloud Run pricing](https://cloud.google.com/run/pricing) for current numbers.

The first request after the service has been idle starts a new instance, which takes about a minute while Trino starts.

Trino is told to reach itself at 127.0.0.1 (`node.internal-address` in `space/Dockerfile`). Without that, on Cloud Run it advertises an internal IPv6 address it can't connect to, and every query times out.

## Running it

| Task | Command |
|---|---|
| Redeploy after a code change | `cloudrun/deploy.sh` |
| Redeploy a settings change, reusing the last image | `SKIP_BUILD=1 cloudrun/deploy.sh` |
| Check the key is required (expect 401) | `curl -s -o /dev/null -w '%{http_code}\n' -X POST <service-url>/mcp` |
| See the service, URL, and revisions | `gcloud run services describe bikelake-mcp --region us-east1` |
| Read recent logs | `gcloud logging read 'resource.labels.service_name="bikelake-mcp"' --limit 50 --freshness 1h` |
| Watch a build | `gcloud builds list --limit 3`, or Cloud Build > History in the console |
| Take it offline | `gcloud run services delete bikelake-mcp --region us-east1` (redeploy to bring it back) |

The same things are in the Google Cloud console under the `bike-lane-lakehouse` project: Cloud Run (service, logs, revisions), Cloud Build (builds), Artifact Registry (images), Secret Manager (credentials, values hidden), and Billing.

Problems hit during the first deploy, and the fixes now in place:

- **"Permission denied" creating the image registry, right after the project was created.** Artifact Registry takes a few minutes to switch on for a new project and reports it as a permission error. Waiting and re-running the script fixed it.
- **Every query timed out.** Trino advertised an internal IPv6 address it couldn't reach. Fixed with `node.internal-address=127.0.0.1`.
- **"Cannot update environment variable ... already set with a different type."** The first deploy stored the catalog URI, warehouse, and endpoint as secrets; they're plain settings now. Cloud Run won't switch a variable between the two in place, so the old secret mappings were removed once (`gcloud run services update --remove-secrets ...`) and the secrets deleted.

## Refreshing the data

The server reads whatever is in R2. To publish new data, materialize the `public/marts` asset in the local Dagster (http://localhost:3000). No redeploy is needed.
