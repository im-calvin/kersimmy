# Kersimmy

A Chinese-to-English manuscript workspace with a shared Docker library, a draft
editor, and native Word comment export.

## Run locally

From the project root with Docker Compose installed:

```sh
docker compose up -d --build --wait
```

Open [the local reader](http://127.0.0.1:8888/) and import a manuscript or restore a
book backup. The `reader_data` Docker volume holds the library, drafts, and
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
   `docker volume create kersimmy`. If you have an existing
   reader on the host, use its existing volume name as `READER_DATA_VOLUME`.
3. In **Projects → Create Project**, name it `kersimmy` and paste
   [compose.arcane.yaml](compose.arcane.yaml). The project publishes the reader
   to `127.0.0.1:8888` on the Docker host.
4. Save the project and click **Up**. Check that the reader container is healthy.
   Point host-installed cloudflared on the same machine at `http://127.0.0.1:8888`.
   See the [production setup guide](DEPLOYMENT.md#production-arcane-and-cloudflare) for
   migration, Access configuration, and rollbacks. [Arcane project documentation](https://getarcane.app/docs/docker/projects)

### Automatic deployment

GitHub Actions tests changes and publishes passing builds to GHCR. For a project
tracking `ghcr.io/im-calvin/kersimmy:latest`, enable **Image Update Watcher** and
**Auto Update** under **Settings → Automations** for its Arcane agent. To pull a
new image immediately after publishing, choose **Redeploy** in the Arcane
project. [Arcane update options](https://getarcane.app/docs/docker/auto-updates)

## Tests

See [tests/README.md](tests/README.md) for local Playwright setup and coverage.
