# SQLite server and Docker deployment

For GitHub Actions, registry images, and automatic deployment, see the
[deployment quick start](README.md#github-actions). The steps below include the
local-image alternative and the detailed Portainer and Cloudflare setup.

The original Python parser and page generators power the reader. A small Python
service provides book setup, SQLite storage, synchronization and backups. It
stores books, drafts, review text, settings, and GIFs centrally.
Use the same server on all devices. New books still use Add manuscript and Preview.

## Docker

From the project directory on a machine with Docker Compose:

```sh
docker compose up -d --build
```

Open http://127.0.0.1:8000/. The named `reader_data` volume stores
`/data/reader.sqlite3` and `/data/backups/`. Rebuilding the image preserves data.
Do not remove the volume (`docker compose down -v` deletes it).

Use `compose.portainer.yaml` for Portainer and follow the steps below. Both
stacks run as UID/GID 10001 with a read-only container filesystem. SQLite and
its snapshots write to the named volume, and manuscript previews use a temporary
filesystem at `/tmp`. The image starts with an empty library. Import a
full-project JSON backup or add a manuscript after launch.

The local stack publishes to loopback only. The Portainer stack joins the existing
connector network. Put Cloudflare Access in front of the reader because the
application has no built-in login.

## Automatic saves, sync, and backups

- Drafts autosave to SQLite after approximately 400 ms of inactivity.
- Open editors check the server every 5 seconds while clean; the library refreshes
  every 10 seconds. Unsaved edits are never silently replaced by remote changes.
- Concurrent stale writes are rejected. Download the conflicting local work with
  Backup before reloading to choose which version to keep.
- Interrupted saves retain a recovery snapshot in browser localStorage and retry
  automatically. Keep the page open until Synced to server. Local recovery also
  survives a reload at the same address. The app must be loaded while online;
  this is not a fully offline application.
- SQLite snapshots run at startup, every 15 minutes, and on orderly Python shutdown.
  BACKUP_INTERVAL_SECONDS and BACKUP_KEEP configure cadence and retention.
  Defaults retain the newest 96 snapshots (roughly one day, less with manual or
  restart snapshots). Snapshots use SQLite's online backup API and integrity
  checks, then atomically rename the finished file. Failed backups are shown in
  the library server status. Back up server now creates an extra snapshot.
- JSON book/library downloads and restores remain available.
- Local Docker also writes version-1 JSON snapshots beside the SQLite files at
  the same interval. These include comments, offsets and italic ranges for
  Restore backup. Set `PORTABLE_JSON_SNAPSHOTS=0` when starting Compose to
  disable the extra files. The file reader can also write snapshots while its tab is
  open. In a supported browser, use View → Choose snapshot folder and set the
  interval. Choose the folder again after reopening the file reader.

Snapshots in the same volume protect against editing mistakes, not host/disk
loss. Copy `/data/backups/` to another disk or include the volume in your existing
server backup job. No external/cloud backup destination is configured.

## Migrate existing drafts

At your original browser address, choose Back up library, then Restore backup on
the SQLite site. The Import browser library button can copy books automatically
when the old IndexedDB data is available at the exact same origin/profile.
Migration preserves browser copies and creates new server copies; run it once
or you will get duplicates. The original reader's full project backup works too.

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

## Portainer Standalone and translate.bxian03.com

This deployment uses your existing cloudflared container; it does not create
another tunnel or need its token. The reader has no published host port in
`compose.portainer.yaml` and is reachable by the connector on its shared network.

1. Copy this project to the Portainer Docker host and build there:

   ```sh
   docker build -t translation-reader:local .
   ```

   Building on the target host also avoids Mac ARM versus server x86 image
   differences. Uploading only the Compose file does not upload/build the app.

2. In Portainer, inspect your cloudflared container's Networks section. Choose an
   existing user-defined bridge network. If it has only Docker's default `bridge`
   network, create a user-defined bridge network called `tunnel` and attach
   cloudflared to it. Include that attachment in cloudflared's own stack so a
   redeployment preserves it.

   If you build on a different machine with the same CPU architecture, transfer
   the image with `docker save -o translation-reader.tar translation-reader:local`
   and run `docker load -i translation-reader.tar` on the Portainer Docker host.
   You can also supply a registry image with `READER_IMAGE` in step 3.

3. Choose Stacks → Add stack, name it `translation-reader`, and paste or upload
   `compose.portainer.yaml`. For an existing deployment, update the existing stack
   under its current name so Compose continues using the same SQLite volume.
   Add this stack environment variable:

   ```text
   CLOUDFLARED_NETWORK=<the network name from step 2>
   ```

   Deploy using the image already on the host and leave **Re-pull image** off
   for `translation-reader:local`. The stack creates `translation-reader_reader_data`
   on a fresh deployment with that stack name. When updating the local image,
   build on the Docker host again, then update the same stack and check that
   the reader container was recreated. You can set `BACKUP_INTERVAL_SECONDS`
   and `BACKUP_KEEP` in Portainer to override the defaults.

4. Before publishing the hostname, configure a Cloudflare Access self-hosted
   application for `translate.bxian03.com` and an Allow policy for your email.
   An email one-time code is a simple option if enabled in your Access login
   methods. This protects the entire application and API; the app itself has
   no username/password login. A tunnel alone does not add authentication.

5. In the existing Cloudflare tunnel's Published application routes (called
   Public Hostnames in some dashboard versions), add:

   ```text
   Subdomain: translate
   Domain: bxian03.com
   Path: leave blank
   Service type: HTTP
   URL: translation-reader:8000
   ```

   The full origin is `http://translation-reader:8000`, not localhost: localhost
   inside cloudflared refers to the connector's own container. Keep the default
   HTTP Host header so browser same-origin checks see the public hostname.

6. Open `https://translate.bxian03.com`, sign in through Access, and restore a JSON
   library backup from the local site. Confirm an edit appears on a second device
   and survives restarting the reader container. Check the library shows automatic
   SQLite backups with no errors. In a private browser window, verify Access
   blocks the site before login.

The public route, Access application, server image build, and Portainer deployment
must still be applied in your infrastructure. These files prepare that setup;
no remote settings were changed from the development workspace.

Official references:
- https://docs.portainer.io/user/docker/stacks/add
- https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/
