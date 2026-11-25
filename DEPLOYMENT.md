# SQLite server and container deployment

For GitHub Actions, registry images, and automatic deployment, see the
[deployment quick start](README.md#github-actions). The steps below include the
local Docker setup and the production Arcane and Cloudflare setup.

The original Python parser and page generators power the reader. A small Python
service provides book setup, SQLite storage, synchronization and backups. It
stores books, drafts, review text, settings, and GIFs centrally.
Use the same server on all devices. New books still use Add manuscript and Preview.

## Docker

From the project directory on a machine with Docker Compose:

```sh
docker compose up -d --build
```

Open http://127.0.0.1:8888/. The named `reader_data` volume stores
`/data/reader.sqlite3` and `/data/backups/`. Rebuilding the image preserves data.
Do not remove the volume (`docker compose down -v` deletes it).

The container runs as UID/GID 10001 with a read-only root filesystem. SQLite
and its snapshots write to the named volume. A fresh volume starts with an
empty library, ready for a manuscript or a book backup.

## Automatic saves, sync, and backups

- Drafts autosave to SQLite after approximately 400 ms of inactivity.
- Open editors check the server every 5 seconds while clean; the library refreshes
  every 10 seconds. Unsaved edits are never silently replaced by remote changes.
- Concurrent stale writes are rejected. The local draft stays open, even after
  a reload. Download a recovery backup to keep it, then choose **Use server
  version** to discard the pending edits and reopen the saved server copy.
- Open a draft online and check the toolbar's save status menu for
  **Available offline**. That draft can then
  reload and be edited offline in the same browser at the same address.
  Interrupted saves retain a recovery snapshot in browser storage and retry
  automatically on reconnect. The library, imports, and previously unopened
  drafts need the server. On a remote host, offline support requires HTTPS.
- SQLite snapshots run at startup, every five minutes, and on orderly Python shutdown.
  BACKUP_INTERVAL_SECONDS and BACKUP_KEEP configure cadence and retention.
- `docker compose logs -f reader` shows startup settings, opened books, imports,
  settings changes, removals, save conflicts, rejected requests, errors, and
  snapshots that contain changes. Draft saves appear at most once per book every
  five minutes. Set `LOG_LEVEL=DEBUG` to also see every HTTP request.
  Defaults retain the newest 96 snapshots (roughly eight hours, less with manual or
  restart snapshots). Snapshots use SQLite's online backup API and integrity
  checks, then atomically rename the finished file. Failed backups are shown in
  the library server status. Snapshot library on server creates an extra SQLite snapshot.
- **Back up library** downloads all books. **Back up book** downloads one
  translation project, including its chapters. Both JSON files can be restored
  with **Restore backup**.
- Local Docker also writes version-1 JSON snapshots beside the SQLite files at
  the same interval. These include comments, offsets and italic ranges for
  Restore backup. Set `PORTABLE_JSON_SNAPSHOTS=0` when starting Compose to
  disable the extra files.
- In a supported browser, open a draft and use **Exports → Choose book backup
  folder** to save that book on your computer. The reader writes a restorable
  JSON file immediately and every five minutes by default while the drafting tab
  stays open. It includes pending edits in that tab. Choose the folder again
  after reloading or reopening the draft. Browser snapshots accumulate in the
  selected folder. Use **Restore backup** in the library to restore one.
  If folder access is unavailable, use **Exports → Back up book** to
  download the same kind of restorable JSON manually.

Server snapshots live in `/data/backups/` in Docker or `data/backups/` when
running directly with the default data directory. They survive a container
replacement with its volume intact. A lost host or disk also takes its snapshots.
Use a browser folder on another machine for the open book, or replicate
`/data/backups/` to another machine for unattended whole-library recovery.

## Migrate existing drafts

At your original browser address, choose Back up library, then Restore backup on
the SQLite site. The Import browser library button can copy books automatically
when the old IndexedDB data is available at the exact same origin/profile.
Migration preserves browser copies and creates new server copies; run it once
or you will get duplicates. The original reader's book backup works too.

## Restore a database snapshot

Stop the app so it cannot write during restoration. The restore command creates
an additional pre-restore snapshot before replacing the live database:

```sh
docker compose stop reader
docker compose run --rm --no-deps reader python tools/restore_reader.py /data/backups/reader-TIMESTAMP.sqlite3
docker compose up -d
```

Replace the filename with a retained snapshot. All browsers must reload after
restoration. JSON backups can instead be restored through the library as new books.

## Run without Docker

```sh
python3 tools/build_web.py
python3 tools/reader_server.py --data ./data
```

Open http://127.0.0.1:8000/. Keep SQLite on local disk, not an SMB/NFS share.
`python3 tools/serve.py` builds the library assets and launches this same Python service.

## Tests

```sh
python3 -m unittest discover -s tests -p server_test.py
```

For end-to-end checks, start a test server on port 8002 with a temporary data
directory, then run `tests/original_reader_test.py`. See web/README.md.

## Production Arcane and Cloudflare

Arcane manages the reader as a Docker Compose project. The project file
[compose.arcane.yaml](compose.arcane.yaml) pulls
`ghcr.io/im-calvin/kersimmy:latest`, runs the reader on port 8888 inside the
container, publishes it at `127.0.0.1:8888` by default, and mounts an external
Docker volume at `/data`.

1. Install Arcane with its [Docker Compose instructions](https://getarcane.app/docs/get-started/installation)
   if it is new to the host. In Arcane, select the Docker agent on the same
   machine as the host-installed cloudflared service.

2. For a fresh library, run `docker volume create kersimmy`
   on the Docker host. For a migration on the same Docker host, find the old
   reader's named volume mounted at `/data` and set `READER_DATA_VOLUME` to that
   name. Set `READER_DATA_VOLUME=translation-reader_reader_data` if that is the
   volume used by your existing project. Back up the library and stop the old
   reader before starting the new project against its volume. To migrate across
   hosts, deploy with a fresh volume and restore a full-library JSON backup.
3. In Arcane, open **Projects → Create Project** and name it
   `kersimmy`. Paste the YAML from [compose.arcane.yaml](compose.arcane.yaml).
   For Git Pull sync, use `kersimmy` as the sync name.
   For an existing project, update its Compose file and remove the old
   `CLOUDFLARED_NETWORK` setting. Set `READER_HOST_PORT` if port 8888 is occupied,
   `READER_DATA_VOLUME` if using a different volume, or `READER_IMAGE` if
   pinning a specific release. Save and click **Up**. The named volume is
   external to this Compose project and persists across redeployments.
   [Arcane project documentation](https://getarcane.app/docs/docker/projects)
4. Protect `translate.bxian03.com` with Cloudflare Access and set the existing
   tunnel origin to `http://127.0.0.1:8888`, using the same port as
   `READER_HOST_PORT` if overridden. Keep the default HTTP Host header.
   Run `curl -fsS http://127.0.0.1:8888/api/status` on the Docker host, then
   confirm the public hostname requires Access sign-in and opens the library.
   [Cloudflare tunnel routing](https://developers.cloudflare.com/tunnel/concepts/routing/)

### Updates and rollback

Test the candidate release with a disposable copy of the previous release's
SQLite database and a version-1 JSON backup before rolling it out. Use the
existing production volume and hostname. Pin a tested `sha-<full commit SHA>`
image for the rollout and keep the previous tag for rollback.

Run the compatibility check with the Git commit currently deployed in production:

```sh
.venv/bin/python tests/release_compatibility.py --previous-ref <deployed-commit>
```

The script creates a synthetic library with the previous release, upgrades it
using the working tree, verifies forward refresh, then rolls back. It uses a
temporary directory, localhost port, and isolated Chromium profile.

The site displays its product version. Change `APP_VERSION` in
`tools/reader_server.py` when releasing a new product version.
Check `/api/status` for both the product version and the running release SHA. Once this update is installed,
clean open tabs reload on later release changes. Tabs with pending edits or open
dialogs wait until they can reload safely. Tabs opened before release detection
was introduced need one refresh to pick it up.

GitHub Actions tests and publishes the images. Arcane pulls and deploys them.
Choose how Arcane checks for updates:

- **Manual**. In the reader's Arcane project, choose **Redeploy** to pull the
  current image and recreate the container.
- **Scheduled**. Keep `READER_IMAGE` on `ghcr.io/im-calvin/kersimmy:latest`.
  Under **Settings → Automations**, select the agent and turn on **Image Update
  Watcher** and **Auto Update**. Check **Excluded Containers** for any other
  workloads on the agent that should keep their current images.
  [Arcane auto-update documentation](https://getarcane.app/docs/docker/auto-updates)

Use Arcane Git Pull sync for changes to `compose.arcane.yaml`. The image watcher
handles new builds published under the same tag when the Compose file stays the
same. After an update, check the reader container's health and `/api/status` on
the Docker host.

For a rollback, set `READER_IMAGE` in Arcane to a known-good
`ghcr.io/im-calvin/kersimmy:sha-<full commit SHA>` tag or digest and redeploy the
same project. A later change back to `latest` resumes updates from that tag.

If the image is made private, add GHCR credentials to Arcane's Container
Registries for the selected agent. Use a classic GitHub token with
`read:packages`.
[GHCR authentication](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-to-the-container-registry)

### Restore an Arcane database snapshot

From the Arcane project directory on the Docker host, use its Compose file and
`.env` to stop the reader and restore a retained SQLite snapshot:

```sh
docker compose stop reader
docker compose run --rm --no-deps reader python tools/restore_reader.py /data/backups/reader-TIMESTAMP.sqlite3
docker compose up -d reader
```

Replace the filename with a saved snapshot. Reload the reader on all devices
after the restore.
