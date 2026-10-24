# loraii / Hosted HTML overlays

This is a separate hosted edition of the full HTML package. It is prepared for
Render; it has not been published or given a live URL yet.

Once deployed, open the hosted controller in your browser and use its private
scene URLs in OBS. START.cmd is not required for hosted chat, graphics, timers,
manual music or plans. OBS continues to handle scene switches and transitions.

## Render setup

1. Connect Render to the source repository (or let the connected Render assistant
   deploy this folder). The repository root must contain Dockerfile, app/ and
   render.yaml.
2. The default render.yaml requests a FREE PREVIEW service and automatically
   generates ADMIN_KEY, VIEW_KEY and LORAII_RELAY_KEY environment secrets.
3. Wait for the service health check at /healthz to pass.
4. Open the service URL. Sign in with ADMIN_KEY from the service environment.
5. In Connections / advanced controls, add your five existing StreamElements
   overlay links, then save. Just Chatting and Highlights use Gameplay.
6. Open Connect StreamElements relay. Replace the old local relay block in your
   custom widget with this hosted relay and save. It contains the deployed
   hostname and hosted relay key. Send a real Twitch message to verify.
7. Download the hosted OBS collection from that same controller, import it into
   OBS and select loraii - Online HTML. Or copy each private source URL into your
   existing scene's Browser Source. Dimensions remain 1920 x 1080.
8. Refresh sources and verify chat, font, background and timer before streaming.

Your original local package is unchanged. Do not replace it with this cloud folder.

## Preview versus persistent production

The free blueprint uses temporary storage. Settings and connections can be lost
when the host sleeps, restarts or redeploys. A notice in the controller explains
that limitation. Use the free version to verify the online workflow.

render-persistent.yaml is the explicit PAID alternative with a persistent disk.
Choose it deliberately in Render (rename it to render.yaml for that deployment).
It stores settings in /var/data. Run one instance only: state and event fanout are
currently designed for one process. No paid service was created by this package.

To configure secrets manually instead of using a Blueprint, generate three
separate random values at least 24 characters long. Set ADMIN_KEY, VIEW_KEY,
LORAII_RELAY_KEY, PORT=10000 and LORAII_DATA_DIR to a writable data directory.
Set PERSISTENT_STORAGE=1 only when that directory is actually persistent.
Optional PUBLIC_URL specifies your canonical HTTPS hostname; Render's public URL
is detected automatically otherwise.

## Protection

The controller requires an admin cookie established through /login. OBS receives
separate private viewer links; viewer access cannot change timers or settings.
Static assets, state, event streams and StreamElements configuration are protected.
Only /login and /healthz are public. Rotating VIEW_KEY invalidates old viewer
sessions. Never share the controller access key or private OBS links publicly.
Existing StreamElements URLs are not embedded in the deployment source; set them
through the protected controller or the optional SE_URLS_JSON environment secret.
No live account secrets have been included in this archive.

## Desktop features

Windows automatic now-playing and local OBS replay-file operations are not run by
the cloud service. Use manual music controls here. An optional desktop bridge can
be added later; its interface is not implemented in this hosted release. Your
native OBS capture/audio sources and scene switching stay in OBS.

## Checks

Local tests covered admin sign-in, cookie and viewer permissions, eight scene
links, protected assets, timers/settings persistence, StreamElements event
forwarding, generated hosted relay code, OBS collection export and origin checks.
These checks do not substitute for a deployed Render/StreamElements/Windows OBS
session. No hosted URL or live Twitch delivery is claimed yet.

## Simple controller

Timer and music are the only expanded control panels. Start becomes Resume after
a pause. Stream plan, scene preview, chat diagnostics and settings stay collapsed.
All eight scene previews and private source links remain available when needed.

## Spotify music widget
The Music panel now offers Spotify Now Playing plus previous/play/pause/next controls. Audio continues to play in the Spotify app and enters OBS through your normal audio routing; the website displays metadata only.

1. Open Music → Spotify setup.
2. Create a Web API app at https://developer.spotify.com/dashboard (app owner needs Spotify Premium). Add this exact redirect URI: `https://loraii-overlays-preview.onrender.com/spotify/callback` (use your own host if different).
3. Paste the app Client ID into the controller, Save Client ID, then Connect Spotify and approve access. Do not provide a client secret.
4. Open Spotify on the PC and play a track. The existing scene banners update automatically and hide on pause. Connecting disables the manual title override; manual mode remains available.

Access/refresh tokens stay on the server, excluded from Git and viewer APIs. Free preview storage may forget authorization after restart; reconnect, or use persistent storage. Playback uses one shared poll every five seconds while the controller/overlays are active, with rate-limit backoff. Spotify sign-in and real playback must be verified with your own account after deployment.

## Cute chat battle — The Little Bonk Club
Open the controller → Cute chat battle → Open lobby. On Starting Soon, Break or Ending, viewers type exactly `!play` through the existing StreamElements relay. One entry per Twitch identity, maximum 40 players. Two players are required. A lobby starts automatically after 45 active seconds, or you can press Start round. Cute cats, frogs, ghosts and blobs automatically chase, bonk and survive a shrinking ring. The winner wears a crown for 15 seconds, then a new lobby opens. Turn off hides and clears the game; Reset opens a fresh lobby. Starts off after a server restart.

Only the three waiting scenes load the game. The server owns simulation and joins, so refreshing or opening another waiting scene does not duplicate the match. Arena state uses memory, not persistent storage. Graphics are compact 2.5D canvas characters above a WebGPU-rendered arena floor; a Canvas floor is used automatically when WebGPU is unavailable or the GPU device is lost. There is no dependency download and no game audio.

In OBS, enable **Shutdown source when not visible** for all three waiting-screen Browser Sources. Active scene heartbeats pause simulation after eight seconds without a waiting screen. Without that setting, a hidden source may remain loaded and keep the game active. OBS source-activity events and document visibility are also observed.

After updating, refresh the three waiting sources and your controller. The Scene preview shows six fictional sample creatures without sending joins or presence to the real game. Test a real `!play` message to verify your StreamElements relay.

Verification: authenticated HTTP relay joins, exact command matching, deduplication, capacity, full match simulation, winner/lobby cycle, pause, permissions, scene asset scope and existing Spotify status checked locally. Canvas sample renderer visually inspected. WebGPU GPU execution and actual Windows OBS rendering still need checking on your PC.
