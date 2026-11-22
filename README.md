# Translation Reader

A Chinese-to-English manuscript workspace with a shared Docker library, a draft
editor, and native Word comment export.

## Run locally

From the project root with Docker Compose installed:

```sh
docker compose up -d --build --wait
```

Open [the local reader](http://127.0.0.1:8000/) and import a manuscript or restore a
project backup. The `reader_data` Docker volume holds the library, drafts, and
snapshots. Keep the volume when upgrading. See [DEPLOYMENT.md](DEPLOYMENT.md) for
backup and restore instructions.

## GitHub Actions

Use a GitHub repository with `main` as its default branch. For a fresh setup,
create it empty, connect it as `origin`, and push the local `main` branch:

```sh
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

The push starts **Reader CI and delivery** under the repository's **Actions** tab.
Pull requests run storage tests, Playwright, and a Docker health check. A passing
run on `main` also publishes an AMD64 and ARM64 image to GitHub Container Registry
with tags `latest` and `sha-<full commit SHA>`. Use **Run workflow** on `main` to
rerun delivery manually. The workflow publishes with GitHub's built-in token.
The repository and image exclude manuscripts, the local book configuration,
database files, and backups. [GitHub image publishing](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)

## Deploy in Arcane

1. Set up Arcane on the Docker host that will run the reader, or pick that host
   as an agent in an existing Arcane installation. [Arcane installation](https://getarcane.app/docs/get-started/installation)
2. Create the reader data volume on that host with
   `docker volume create translation-reader_reader_data`. If you have an existing
   reader on the host, use its existing volume name as `READER_DATA_VOLUME`.
3. In **Projects → Create Project**, name it `translation-reader` and paste
   [compose.arcane.yaml](compose.arcane.yaml). Add an `.env` file with the name of
   the Docker network shared with cloudflared. For example:

   ```dotenv
   CLOUDFLARED_NETWORK=tunnel
   ```

4. Save the project and click **Up**. Check that the reader container is healthy.
   Route the Cloudflare tunnel to `http://translation-reader:8000`. See the
   [production setup guide](DEPLOYMENT.md#production-arcane-and-cloudflare) for
   migration, Access configuration, and rollbacks. [Arcane project documentation](https://getarcane.app/docs/docker/projects)

### Automatic deployment

For an immediate redeploy after images publish, create a **Project → Redeploy**
webhook in Arcane under **System → Webhooks**. Save the full URL as
`ARCANE_WEBHOOK_URL` in the GitHub `production` environment and set the
repository Actions variable `ARCANE_DEPLOY_ENABLED` to `true`. GitHub Actions calls
the webhook after a successful publish. Arcane records the background
deployment result in its Event Log. [Arcane webhook documentation](https://getarcane.app/docs/reference/api#inbound-webhooks)

For a private Arcane dashboard, use Arcane's scheduled image updates or choose
**Redeploy** in the project after a publish. [Arcane update options](https://getarcane.app/docs/docker/auto-updates)

## Tests

See [tests/README.md](tests/README.md) for local Playwright setup and coverage.
