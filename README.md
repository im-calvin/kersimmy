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

## Deploy the image in Portainer

1. After the first successful publish, add `ghcr.io` as a registry in Portainer.
   For a private image, use a GitHub account with access to the package and a
   classic personal access token with `read:packages`. Store the token in Portainer.
   [GitHub registry authentication](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-to-the-container-registry)
2. In **Stacks**, update the existing reader stack or create one named
   `translation-reader`. Use [compose.portainer.yaml](compose.portainer.yaml).
   Keep the existing stack name and `reader_data` volume so the new image opens
   the same database. Set these stack environment variables:

   ```dotenv
   READER_IMAGE=ghcr.io/owner/repository:latest
   CLOUDFLARED_NETWORK=your-existing-tunnel-network
   ```

3. Enable **Re-pull image** when deploying or updating the registry-backed stack.
   Keep Cloudflare Access enabled before routing public traffic to the reader.
   The [Portainer and tunnel setup](DEPLOYMENT.md#portainer-standalone-and-translatebxian03com)
   describes the network and route. Verify the new container reports healthy and
   the existing library opens. [Portainer stack setup](https://docs.portainer.io/user/docker/stacks/add)
4. To roll back, set `READER_IMAGE` to the last known-good `sha-<full commit SHA>`
   image and update the same stack.

### Optional automatic deployment

For a Git-backed Portainer stack, point it to `main` and `compose.portainer.yaml`.
Enable **GitOps updates**, choose **Webhook**, and enable **Re-pull image** and
**Force redeployment** so a rebuilt image can be pulled even when Git has no new
commit. For an existing editor-managed stack, use its stack webhook if your
Portainer edition supports it. Keep the Portainer dashboard private and use an
HTTPS webhook reachable from the GitHub runner. [Portainer GitOps options](https://docs.portainer.io/user/docker/stacks/add#gitops-updates), [Portainer stack webhooks](https://docs.portainer.io/user/docker/stacks/webhooks)

In GitHub, create a `production` environment and add the webhook URL as its
`PORTAINER_WEBHOOK_URL` secret. Set the repository Actions variable
`PORTAINER_DEPLOY_ENABLED` to `true`. GitHub requests a redeploy only after the
image is published. Check the Portainer stack's health after the webhook runs.
Leave the variable unset for manual deployment and rollbacks.

## Tests

See [tests/README.md](tests/README.md) for local Playwright setup and coverage.
