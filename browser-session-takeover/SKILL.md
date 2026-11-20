---
name: browser-session-takeover
description: Use when an automation task needs a browser where the user is already signed in, such as cloud consoles, OAuth grants, or developer portals. Attaches to the visible browser so the task does not hit login walls. macOS.
license: MIT
compatibility: macOS. Chrome for Testing or another Chromium browser, reached through a debug port, or through AppleScript with JavaScript from Apple Events enabled. Needs shell, osascript, and CDP access.
---

# Driving the user's signed-in browser

Use this for work that needs the user's existing session: cloud consoles, OAuth grants, developer portals. A fresh automation profile hits login walls, bot challenges, and MFA. The user's own browser does not. The user still does the credential steps. This skill covers how to attach, drive, and hand off.

## Rules

- The user types passwords and approves MFA. Never enter a credential. Stage the login URL, hand off, and wait for the go-ahead.
- Check the URL after every navigation. A session that looked live can have expired, and the page then shows a login form.
- Do not scrape rendered pages when the site has a same-origin JSON API. The API returns structured data and avoids layout breakage.
- Keep each tool call that waits under about 60 seconds. A long sleep inside one call can drop the CDP socket (`no close frame received`), and the browser restarts without the session. Poll across separate calls.

## Step 1: Find the right instance

Several browser instances can run at once, and the one your automation controls may be windowless while a different instance is on screen. Confirm which one you are attached to.

```bash
osascript -e 'tell application "Google Chrome for Testing" to get URL of tabs of window 1'
```

If AppleScript and CDP disagree about the open tabs, you are attached to the wrong instance. Stop and fix that before doing anything else.

The visible instance also responds to AppleScript directly:

```applescript
tell application "Google Chrome for Testing"
  set URL of active tab of window 1 to "https://console.example.com"
  make new tab at end of tabs of window 1 with properties {URL:"https://..."}
end tell
```

## Step 2: Attach over CDP (Chrome with a debug port)

If `--user-data-dir` does not appear in the process list, or no `DevToolsActivePort` file exists, the instance has no debug port. Skip to Step 3 and use AppleScript.

1. Find the running instance and its profile directory:

```bash
ps aux | grep "Chrome for Testing.app/Contents/MacOS" | grep -o -- '--user-data-dir=[^ ]*'
```

2. The first line of `<user-data-dir>/DevToolsActivePort` is the port. The file exists even when Chrome started with `--remote-debugging-port=0`.
3. List tabs: `curl -s http://127.0.0.1:<port>/json/list`. Pick the target by URL.
4. Connect with `websocket.create_connection(ws_url, suppress_origin=True)`. Without `suppress_origin`, Chrome returns 403 for the unknown Origin header.
5. Evaluate with `Runtime.evaluate` and `returnByValue=True`. Add `awaitPromise=True` for async code. Take a screenshot with `Page.captureScreenshot` and check it visually when the DOM is unclear.

```python
import json, urllib.request, websocket
port = 9222  # read from DevToolsActivePort
tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list"))
page = next(t for t in tabs if t["type"] == "page" and "console.example.com" in t["url"])
ws = websocket.create_connection(page["webSocketDebuggerUrl"], suppress_origin=True)
ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                    "params": {"expression": "document.title", "returnByValue": True}}))
print(json.loads(ws.recv())["result"]["result"]["value"])
```

## Step 3: Drive a browser without a debug port

Some Chromium browsers expose no debug port. AppleScript can still run JavaScript in a tab, once the user turns on the setting.

1. Ask the user to choose View > Developer > Allow JavaScript from Apple Events. It is one click.
2. Pick the tab by URL prefix. Loop over `tabs of window 1` and match on `URL`. Do not rely on the active tab.
3. Wrap each `execute` call: `with timeout of 60 seconds`. Background tabs answer slowly, and the default AppleEvent timeout kills the call.
4. AppleScript cannot return the result of an async call. Start the async work and store the result on the page:

```javascript
(async () => {
  const orgs = await (await fetch('/api/organizations')).json();
  window.__x = JSON.stringify(orgs);
})();
```

   Then run a second `execute` that returns `window.__x`, and a third that runs `delete window.__x`.
5. Keep this in a file, not inline. `osascript -e` breaks on quotes and `$`. Run it with `timeout 60 osascript file.applescript`.
6. Read the active tab with `tab -1 of window 1`. Enumerating `tabs of windows` can time out on a busy browser.

## Step 4: Interaction patterns that fail silently

These controls ignore a bare `.click()`. Use the event sequence or a coordinate click.

- **Angular Material and `cfc-select` menus.** Dispatch `pointerdown`, `mousedown`, `pointerup`, `mouseup`, and `click` at the element's center, taken from `getBoundingClientRect()`. Options then appear as `[role=option]`. Match the one you want by its text.
- **Coordinate clicks on dialogs.** A click at the button's center, taken from its bounding rect, works reliably. After each confirm, read the page or take a screenshot. Many admin consoles close a dialog with no confirmation toast when the operation is async.
- **Search dialogs.** Pressing Enter does nothing. Click the Search button.
- **Consent screens.** Before clicking Continue, confirm the summary shows the intended client ID. Several clients in one project can share the same display name, so the ID is the only reliable identifier.

## Step 5: Sign-in flows

- **Google identifier page.** The field is `#identifierId` (type text, not email). Fill it, then click Next by its text. Setting the value through a hand-rolled native setter can throw `Illegal invocation`, so use the field's own input method.
- **Account index.** Check the `authuser` parameter after sign-in. The wrong index opens another account's password challenge.
- **"Sign in with Google" on a third-party site.** The chooser opens in a new target, not the current tab. Find it with `Target.getTargets`, then call `Target.activateTarget` and `Target.attachToTarget` with `flatten=True`. Drive the new target with its session ID. A JS `.click()` on the chooser row does nothing, so click at the element's coordinates with `Input.dispatchMouseEvent`. The Allow button stays `disabled` until its tab is active.
- **Session expiry.** Sessions expire after long gaps or after switching sites. If a login page appears, re-run the identifier step and the password step from the password manager, and click Next. Do not treat a login page as an empty page.
- **Failed social login.** After two bounces or a challenge loop, stop scripting. Hand the flow to the user and let them click through by hand.
- **Which account the login binds.** An organization email can log into a linked personal account that lacks the organization role. Organization settings pages return 404 to outsiders, not 403. A 404 on an org page is a permissions result, so confirm the account before debugging the page.

## Secrets

Values read from a page, such as a generated key, must not touch disk. Stash the value on `window.__x`, read it into process memory, send it to its destination, and verify the destination stored a reference rather than the raw value. Then clear `window.__x`.

## Handoff checklist

- The URL and account are what the task expects.
- Every step that needed a credential was done by the user.
- Any value that was read was sent where it belonged and not logged.
- The browser instance you drove is the one the user can see, or you say so.
