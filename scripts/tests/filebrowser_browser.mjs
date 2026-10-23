// Disposable UI isolation test using Chromium CDP; no npm dependencies.
// Fixture tokens arrive on stdin only, never command-line args or environment.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

let input = "";
for await (const chunk of process.stdin) input += chunk;
const { base, sessions } = JSON.parse(input);
assert.match(base, /^http:\/\/127\.0\.0\.1:\d+$/);
assert.deepEqual(Object.keys(sessions).sort(), ["alice", "bob"]);
const profile = await mkdtemp(join(tmpdir(), "filebrowser-ui-fixture-"));
const env = Object.fromEntries(["PATH", "HOME", "LANG"].filter(k => process.env[k]).map(k => [k, process.env[k]]));
const chrome = spawn(process.env.CHROMIUM_PATH ?? "chromium", [
    "--headless=new", "--no-first-run", "--no-default-browser-check",
    "--disable-background-networking", "--disable-component-update",
    "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
    "--remote-debugging-pipe", `--user-data-dir=${profile}`, "about:blank",
], { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"], env });
let nextId = 0, buffer = "";
const pending = new Map();
chrome.on("error", () => {
    for (const request of pending.values()) request.reject(new Error("Chromium could not start"));
});
chrome.stdio[4].on("data", chunk => {
    buffer += chunk.toString();
    let end;
    while ((end = buffer.indexOf("\0")) >= 0) {
        const raw = buffer.slice(0, end); buffer = buffer.slice(end + 1);
        if (!raw) continue;
        const message = JSON.parse(raw);
        const request = pending.get(message.id);
        if (!request) continue;
        clearTimeout(request.timer); pending.delete(message.id);
        if (message.error) request.reject(new Error(`CDP ${request.method} failed`));
        else request.resolve(message.result ?? {});
    }
});
function send(method, params = {}, sessionId) {
    const id = ++nextId;
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            pending.delete(id); reject(new Error(`CDP ${method} timed out`));
        }, 15000);
        pending.set(id, { resolve, reject, timer, method });
        chrome.stdio[3].write(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }) + "\0");
    });
}
async function evaluate(session, expression) {
    const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true }, session);
    assert.equal(result.exceptionDetails, undefined, "Browser evaluation failed");
    return result.result.value;
}
try {
    await send("Browser.getVersion");
    for (const [name, token] of Object.entries(sessions)) {
        const other = name === "alice" ? "bob" : "alice";
        const { browserContextId } = await send("Target.createBrowserContext");
        const { targetId } = await send("Target.createTarget", { url: "about:blank", browserContextId });
        const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
        await send("Page.enable", {}, sessionId);
        await send("Runtime.enable", {}, sessionId);
        await send("Network.enable", {}, sessionId);
        await send("Network.setCookie", { url: base, name: "filebrowser_quantum_jwt", value: token, httpOnly: true, sameSite: "Lax" }, sessionId);
        await send("Page.navigate", { url: base + "/" }, sessionId);
        let state;
        for (let attempt = 0; attempt < 80; attempt++) {
            await new Promise(resolve => setTimeout(resolve, 100));
            try {
                state = await evaluate(sessionId, `(() => ({
                    own: new RegExp("\\\\b" + ${JSON.stringify(name)} + "\\\\b", "i").test(document.body.innerText),
                    foreign: new RegExp("\\\\b" + ${JSON.stringify(other)} + "\\\\b", "i").test(document.body.innerText),
                    file: document.body.innerText.includes("retained.txt"),
                    path: location.pathname
                }))()`);
                if (state.file) break;
            } catch { /* Navigation can destroy the initial execution context. */ }
        }
        assert.equal(state?.file, true, `UI file listing did not load for ${name}; path=${state?.path}`);
        assert.equal(state.foreign, false, "UI exposed another user's source");
        const result = await evaluate(sessionId, `(async () => {
            const self = await fetch('/api/users?username=self').then(r => r.json());
            const foreign = await fetch('/api/resources?source=${other}&path=/');
            return { username: self.username, sources: self.scopes.map(s => s.name), denied: foreign.status };
        })()`);
        assert.equal(result.username, name);
        assert.deepEqual(result.sources, [name]);
        assert.ok([400, 403, 404].includes(result.denied), "Browser API escaped its source");
        await send("Target.disposeBrowserContext", { browserContextId });
        console.log(`PASS Chromium ${name}: own file listing, no foreign source, cross-source API denied`);
    }
} finally {
    if (chrome.exitCode === null && chrome.signalCode === null) {
        chrome.kill();
        await new Promise(resolve => chrome.once("exit", resolve));
    }
    for (const request of pending.values()) clearTimeout(request.timer);
    await rm(profile, { recursive: true, force: true });
}
