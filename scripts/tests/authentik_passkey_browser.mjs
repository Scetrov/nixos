// Real native Authentik UI + Chromium virtual authenticators. No npm dependencies.
// Invoke only through run_authentik_passkey_browser.py's disposable local fixture.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const base = process.env.AUTHENTIK_BROWSER_TEST_URL;
const password = process.env.AUTHENTIK_BROWSER_TEST_PASSWORD;
if (process.env.AUTHENTIK_BROWSER_TEST_FIXTURE !== "1" ||
    !/^http:\/\/localhost:\d+$/.test(base ?? "") || !password) {
    throw new Error("Only the disposable localhost fixture is supported");
}
const profile = await mkdtemp(join(tmpdir(), "authentik-passkey-browser-"));
const browserEnv = Object.fromEntries(["PATH", "HOME", "LANG"].filter(k => process.env[k]).map(k => [k, process.env[k]]));
const chrome = spawn(process.env.CHROMIUM_PATH ?? "chromium", [
    "--headless=new", "--no-first-run", "--no-default-browser-check",
    "--disable-background-networking", "--disable-component-update",
    "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost",
    "--remote-debugging-pipe", `--user-data-dir=${profile}`, "about:blank",
], { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"], env: browserEnv });

let nextId = 0, buffer = "", session, scriptId, failures = 0, contextId, targetId, resident;
let state = { components: [], assertions: 0, assertionResults: 0, errors: 0, conditional: 0, createRequests: 0, getRequests: 0 };
let savedAssertion;
const pending = new Map();
chrome.on("error", () => {
    for (const p of pending.values()) p.reject(new Error("Chromium could not start"));
});
chrome.stdio[4].on("data", chunk => {
    buffer += chunk.toString();
    let at;
    while ((at = buffer.indexOf("\0")) >= 0) {
        const raw = buffer.slice(0, at); buffer = buffer.slice(at + 1);
        if (!raw) continue;
        const message = JSON.parse(raw);
        if (message.id) {
            const request = pending.get(message.id);
            if (!request) continue;
            clearTimeout(request.timer); pending.delete(message.id);
            if (message.error) {
                // Fixed categories only: never echo arbitrary protocol payloads.
                const reason = message.error.message ?? "";
                const category = reason.includes("Execution context was destroyed") ? "context destroyed"
                    : reason.includes("Cannot find context with specified id") ? "context missing"
                    : reason.includes("Inspected target navigated or closed") ? "target navigated"
                    : "unclassified";
                request.reject(new Error(`CDP ${request.method} failed (${category})`));
            } else request.resolve(message.result ?? {});
        } else if (message.method === "Runtime.exceptionThrown") {
            const details = message.params.exceptionDetails;
            const description = details.exception?.description ?? "";
            const property = description.match(/reading '([A-Za-z_]{1,40})'/)?.[1];
            (state.jsErrors ??= []).push({ type: details.exception?.className ?? "Error", property, line: details.lineNumber });
        } else if (message.method === "Runtime.bindingCalled" && message.params.name === "__passkeyTestEvent") {
            const event = JSON.parse(message.params.payload);
            if (event.kind === "component") state.components.push(event.value);
            if (event.kind === "password-check") state.passwordMatch = event.value;
            if (event.kind === "request-shape") state.lastFields = event.fields;
            if (event.kind === "conditional") state.conditional++;
            if (event.kind === "get-request") state.getRequests++;
            if (event.kind === "get-result") state.getResult = event.present;
            if (event.kind === "get-error") state.getError = event.name;
            if (event.kind === "create") state.createRequests++;
            if (event.kind === "assertion") { state.assertions++; savedAssertion = event.value; }
            if (event.kind === "assertion-result") { state.assertionResults++; if (event.errors) state.errors++; }
        }
    }
});
function send(method, params = {}, targetSession = session) {
    const id = ++nextId;
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            pending.delete(id); reject(new Error(`CDP ${method} timed out`));
        }, 20000);
        pending.set(id, { resolve, reject, timer, method });
        chrome.stdio[3].write(JSON.stringify({ id, method, params, ...(targetSession ? { sessionId: targetSession } : {}) }) + "\0");
    });
}
async function evaluate(expression) {
    const response = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (response.exceptionDetails) throw new Error("Browser evaluation failed");
    return response.result?.value;
}
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(check, label, timeout = 15000) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
        try {
            if (await check()) return;
        } catch (error) {
            // A successful redirect can destroy an in-flight read-only poll.
            // Retry only this observed protocol race, within the same deadline;
            // never turn application errors or authentication denial into success.
            if (error.message !== "CDP Runtime.evaluate failed (target navigated)") throw error;
        }
        await sleep(100);
    }
    throw new Error(`Timed out: ${label}`);
}
// Query native shadow DOM without altering its UI or authentication semantics.
const deep = `(selector) => {
    const visit = (root, query) => {
        if (!root) return null;
        const found = [...root.querySelectorAll(query)].find(element => element.checkVisibility({checkVisibilityCSS:true}));
        if (found) return found;
        for (const node of root.querySelectorAll('*')) {
            if (node.shadowRoot) { const hit = visit(node.shadowRoot, query); if (hit) return hit; }
        }
        return null;
    };
    // Explicit stage scope avoids password-manager decoy inputs and controls
    // from a previous challenge while the native executor is transitioning.
    let root = document, found;
    for (const query of selector.split(' >> ')) {
        found = visit(root, query);
        if (!found) return null;
        root = found.shadowRoot ?? found;
    }
    return found;
}`;
async function exists(selector) {
    return evaluate(`Boolean((${deep})(${JSON.stringify(selector)}))`);
}
async function click(selector) {
    await until(() => exists(selector), "native action available");
    await evaluate(`(${deep})(${JSON.stringify(selector)}).click()`);
}
async function fill(selector, value) {
    await until(() => exists(selector), "native input available");
    await evaluate(`(() => { const e = (${deep})(${JSON.stringify(selector)}); e.focus(); e.select(); })()`);
    await send("Input.insertText", { text: value });
    assert.ok(await evaluate(`(${deep})(${JSON.stringify(selector)}).value === ${JSON.stringify(value)}`), "Native input received fixture value");
}
async function authenticated(username = "passkey-browser-fixture") {
    return evaluate(`(async () => {
        const response = await fetch('/api/v3/core/users/me/');
        if (!response.ok) return false;
        return (await response.json()).user?.username === ${JSON.stringify(username)};
    })()`);
}
async function authenticatedRedirect(username = "passkey-browser-fixture", target = null) {
    // Do not poll the user API during login. A stale anonymous response can
    // expire the new session cookie after the login response has installed it.
    await until(() => evaluate(`location.origin === ${JSON.stringify(base)}
        && document.readyState === 'complete'
        && !location.pathname.startsWith('/if/flow/')
        && !location.pathname.startsWith('/flows/')
        && (${target === null ? "true" : `location.pathname + location.search === ${JSON.stringify(target)}`})`), "native final redirect landed");
    assert.equal(await authenticated(username), true, "Final native redirect must have an authenticated session");
}
async function instrument({ conditional = false, mode = "valid", replay = null } = {}) {
    if (scriptId) await send("Page.removeScriptToEvaluateOnNewDocument", { identifier: scriptId });
    const source = `(() => {
        const report = value => window.__passkeyTestEvent(JSON.stringify(value));
        const config = ${JSON.stringify({ conditional, mode, replay, expectedPassword: password })};
        if (window.PublicKeyCredential) {
            // Exercise both native client feature-detection branches. This does
            // not claim headless Chromium can select an OS autofill suggestion.
            PublicKeyCredential.isConditionalMediationAvailable = async () => config.conditional;
        }
        const get = navigator.credentials.get.bind(navigator.credentials);
        navigator.credentials.get = options => {
            report({kind:'get-request'});
            if (options?.mediation === 'conditional') report({kind:'conditional'});
            if (options?.publicKey) options.publicKey.timeout = 2500;
            if (config.mode === 'cancel') return Promise.reject(new DOMException('Fixture cancellation', 'NotAllowedError'));
            return get(options).then(credential => {
                report({kind:'get-result',present:!!credential});
                return credential;
            }).catch(error => {
                report({kind:'get-error',name:['NotAllowedError','InvalidStateError','SecurityError','AbortError'].includes(error.name) ? error.name : 'OtherError'});
                throw error;
            });
        };
        const create = navigator.credentials.create.bind(navigator.credentials);
        navigator.credentials.create = options => {
            report({kind:'create'});
            if (options?.publicKey) options.publicKey.timeout = 2500;
            return create(options);
        };
        const original = window.fetch.bind(window);
        window.fetch = async (url, init) => {
            const executor = String(url).includes('/flows/executor/');
            let assertion = false;
            if (executor && init?.body && typeof init.body === 'string') {
                const payload = JSON.parse(init.body);
                report({kind:'request-shape',fields:Object.keys(payload).filter(k => /^[a-z_]{1,40}$/.test(k))});
                if ('password' in payload) report({kind:'password-check',value:payload.password === config.expectedPassword});
                const credential = payload.passkey || payload.webauthn;
                if (credential) {
                    assertion = true;
                    report({kind:'assertion',value:payload});
                    if (config.mode === 'invalid') {
                        const signature = credential.response.signature;
                        credential.response.signature = (signature[0] === 'A' ? 'B' : 'A') + signature.slice(1);
                    }
                    if (config.mode === 'unknown') {
                        credential.id = 'dW5rbm93bi1maXh0dXJlLWNyZWRlbnRpYWw';
                        credential.rawId = credential.id;
                    }
                    init = {...init, body:JSON.stringify(config.mode === 'replay' ? config.replay : payload)};
                }
            }
            const response = await original(url, init);
            if (executor) {
                try {
                    const body = await response.clone().json();
                    if (body.component) report({kind:'component', value:body.component});
                    if (assertion) report({kind:'assertion-result', errors: Boolean(body.response_errors && Object.keys(body.response_errors).length)});
                } catch { if (assertion) report({kind:'assertion-result',errors:true}); }
            }
            return response;
        };
    })();`;
    scriptId = (await send("Page.addScriptToEvaluateOnNewDocument", { source })).identifier;
    state = { components: [], assertions: 0, assertionResults: 0, errors: 0, conditional: 0, createRequests: 0, getRequests: 0 };
}
async function navigate(path) {
    await send("Page.navigate", { url: base + path });
}
async function reset(options) {
    // Isolate cookie jars completely: responses from an earlier test must never
    // recreate a session during a denial test. Carry only the virtual hardware
    // credential in memory, just as a real key survives a fresh browser profile.
    const credentials = resident ? (await send("WebAuthn.getCredentials", { authenticatorId: resident })).credentials : [];
    if (targetId) await send("Target.closeTarget", { targetId }, null);
    if (contextId) await send("Target.disposeBrowserContext", { browserContextId: contextId }, null);
    contextId = (await send("Target.createBrowserContext", {}, null)).browserContextId;
    targetId = (await send("Target.createTarget", { url: "about:blank", browserContextId: contextId }, null)).targetId;
    session = (await send("Target.attachToTarget", { targetId, flatten: true }, null)).sessionId;
    scriptId = undefined;
    await send("Page.enable"); await send("Runtime.enable"); await send("Network.enable");
    await send("Page.bringToFront");
    await send("Emulation.setFocusEmulationEnabled", { enabled: true });
    await send("Runtime.addBinding", { name: "__passkeyTestEvent" });
    await send("WebAuthn.enable", { enableUI: false });
    resident = (await send("WebAuthn.addVirtualAuthenticator", { options: {
        protocol: "ctap2", transport: "usb", hasResidentKey: true,
        hasUserVerification: true, automaticPresenceSimulation: true, isUserVerified: true,
    } })).authenticatorId;
    for (const credential of credentials) await send("WebAuthn.addCredential", { authenticatorId: resident, credential });
    await instrument(options);
}
async function fallbackLogin(username = "passkey-browser-fixture") {
    await navigate("/if/flow/default-authentication-flow/");
    await fill('input[name="uidField"]', username);
    await click('button[type="submit"]');
    await fill('ak-stage-password >> input[name="password"]', password);
    await click('ak-stage-password >> button[type="submit"]');
    await until(() => state.components.includes("xak-flow-redirect"), "native fallback completed");
    await authenticatedRedirect(username);
}
async function explicitLogin(query = "") {
    await navigate("/if/flow/passkey-first-candidate/" + query);
}
async function rejectAssertion(mode, options = {}, overrideBits, entryPath) {
    await reset({ mode, ...options });
    if (overrideBits) await send("WebAuthn.setResponseOverrideBits", { authenticatorId: resident, ...overrideBits });
    if (entryPath) await navigate(entryPath);
    else await explicitLogin();
    await until(() => state.assertionResults > 0, "server evaluated rejected assertion");
    assert.equal(await authenticated(), false, "Rejected assertion must not establish a session");
    assert.ok(state.errors > 0, "Native assertion validation must report rejection");
}
async function test(name, work) {
    try { await work(); console.log(`PASS: ${name}`); }
    catch (error) {
        const components = state.components.filter(value => /^(ak-stage-|xak-flow-)[a-z-]+$/.test(value));
        const cookies = await send("Network.getCookies", { urls: [base] });
        const cookieNames = cookies.cookies.map(cookie => cookie.name).filter(value => /^authentik_[a-z_]+$/.test(value));
        const meStatus = await evaluate(`fetch('/api/v3/core/users/me/').then(response => response.status)`);
        console.log(`FAIL: ${name} (${error.message}; native stages: ${components.join(", ")}; fixture password submitted correctly: ${state.passwordMatch === true}; submitted fields: ${(state.lastFields ?? []).join(", ")}; cookie names: ${cookieNames.join(", ")}; me status: ${meStatus}; WebAuthn returned credential: ${state.getResult === true}; WebAuthn error: ${state.getError ?? 'none'}; JS errors: ${JSON.stringify(state.jsErrors ?? [])})`);
        failures++;
    }
}

try {
    await send("Browser.getVersion", {}, null);
    await test("existing password route remains usable before enrollment", async () => {
        await reset(); await fallbackLogin();
        assert.ok(state.components.includes("ak-stage-password"));
    });
    await test("authorized enrollment creates a discoverable user-verified passkey", async () => {
        await navigate("/if/flow/passkey-enrollment-candidate/");
        await until(async () => (await send("WebAuthn.getCredentials", { authenticatorId: resident })).credentials.length === 1, "virtual credential enrolled");
        await until(async () => !(await exists("ak-stage-authenticator-webauthn")), "server accepted registration");
        const credentials = (await send("WebAuthn.getCredentials", { authenticatorId: resident })).credentials;
        assert.ok(credentials[0].isResidentCredential);
    });
    await test("unauthorized enrollment cannot register for a supplied account identifier", async () => {
        await reset();
        await navigate("/if/flow/passkey-enrollment-candidate/?uid_field=passkey-browser-fixture");
        await until(async () => (await exists('input[name="uidField"]')) || (await exists('ak-stage-access-denied')), "authentication gate for enrollment");
        assert.equal(state.createRequests, 0);
        assert.equal((await send("WebAuthn.getCredentials", { authenticatorId: resident })).credentials.length, 1);
        assert.equal(await authenticated(), false);
    });
    {
        // Exercise the actual production resource text with synthetic identity
        // and an existing authenticated endpoint as a return destination.
        const returnTarget = "/api/v3/core/users/me/?native_footer_return=1";
        const fallbackPath = "/if/flow/passkey-first-candidate/?use_password=1";
        const fallbackLink = `ak-brand-links a[href="${fallbackPath}"]`;
        const entry = "/flows/-/default/authentication/?next=" + encodeURIComponent(returnTarget);
        await test("native flow: selected entry automatically attempts a passkey", async () => {
            await reset(); await navigate(entry);
            await until(() => state.getRequests > 0 && state.components.includes("xak-flow-redirect"), "automatic native passkey login");
            await authenticatedRedirect("passkey-browser-fixture", returnTarget);
            assert.ok(!state.components.includes("ak-stage-identification"));
            assert.ok(!state.components.includes("ak-stage-password"));
            assert.equal(state.assertions, 1, "One user-verified assertion must suffice");
            await until(() => evaluate(`location.pathname + location.search === ${JSON.stringify(returnTarget)}`), "passkey preserves return target");
        });
        const replay = savedAssertion;
        await test("legacy explicit URL redirects natively and retains the destination", async () => {
            await reset();
            await navigate("/if/flow/passkey-explicit-candidate/?next=" + encodeURIComponent(returnTarget));
            await authenticatedRedirect("passkey-browser-fixture", returnTarget);
            assert.ok(!state.components.includes("ak-stage-password"));
        });
        await test("native flow: cancellation exposes password fallback without browser Back", async () => {
            await reset({ mode: "cancel" }); await navigate(entry);
            await until(() => state.getRequests > 0, "native prompt attempted");
            await until(() => evaluate(`(${deep})('ak-stage-authenticator-validate-webauthn')?.shadowRoot?.textContent.includes('Retry authentication')`), "native cancellation retry screen");
            assert.equal(await authenticated(), false);
            await until(() => exists(fallbackLink), "native footer fallback link");
            assert.equal(await evaluate(`(${deep})(${JSON.stringify(fallbackLink)}).textContent.trim()`), "Use username/password instead");
            // Stop simulating cancellation on subsequent documents so the
            // unchanged password fallback can perform its normal WebAuthn MFA.
            await instrument();
            await click(fallbackLink);
            await until(() => exists('ak-stage-identification >> h1'), "fallback heading rendered");
            assert.ok(await evaluate(`(${deep})('ak-stage-identification >> h1').textContent.trim() === 'Sign in'`),
                "Shared flow heading must not claim passkey login during password fallback");
            await fill('input[name="uidField"]', "passkey-browser-fixture");
            await click('button[type="submit"]');
            await fill('ak-stage-password >> input[name="password"]', password);
            await click('ak-stage-password >> button[type="submit"]');
            await until(() => state.components.includes("xak-flow-redirect"), "native footer fallback completed");
            await authenticatedRedirect();
            assert.ok(state.components.includes("ak-stage-password"));
            assert.ok(state.components.includes("ak-stage-authenticator-validate"));
        });
        await test("native flow: fallback preserves the original return target", async () => {
            assert.ok(await evaluate(`location.pathname + location.search === ${JSON.stringify(returnTarget)}`),
                "Native footer lost the original application return destination");
        });
        {
            await test("native flow: completed login does not leak its destination into a later login", async () => {
                // Keep the same browser/session history and virtual hardware.
                // Native logout, not a fresh cookie jar, separates transactions.
                const loggedOutTarget = "/api/v3/core/brands/current/";
                await send("WebAuthn.setAutomaticPresenceSimulation", { authenticatorId: resident, enabled: false });
                await navigate("/flows/-/default/invalidation/");
                // Logout clears its query/session and returns to the selected
                // login flow. Prevent virtual hardware from instantly logging
                // back in, then cancel that fresh plan through the native route.
                await until(() => exists("ak-stage-authenticator-validate-webauthn"), "logout returned to native entry");
                assert.equal(await authenticated(), false);
                await navigate("/flows/-/cancel/?next=" + encodeURIComponent(loggedOutTarget));
                await until(() => evaluate(`location.pathname === ${JSON.stringify(loggedOutTarget)} && document.readyState === 'complete'`), "native cancellation completed");
                await send("WebAuthn.setAutomaticPresenceSimulation", { authenticatorId: resident, enabled: true });
                const nextTarget = "/api/v3/core/users/me/?native_footer_return=2";
                await navigate("/flows/-/default/authentication/?next=" + encodeURIComponent(nextTarget));
                await authenticatedRedirect("passkey-browser-fixture", nextTarget);
                await until(() => evaluate(`location.pathname + location.search === ${JSON.stringify(nextTarget)}`), "new transaction owns its return target");
            });
            await test("native flow: fallback cannot replace an active plan's return target", async () => {
                await reset({ mode: "cancel" }); await navigate(entry);
                await until(() => state.getRequests > 0, "native prompt attempted");
                await until(() => exists(fallbackLink), "native footer available");
                await instrument();
                await navigate(fallbackPath + "&next=" + encodeURIComponent("/api/v3/core/users/me/?untrusted_replacement=1"));
                await fill('input[name="uidField"]', "passkey-browser-fixture");
                await click('button[type="submit"]');
                await fill('ak-stage-password >> input[name="password"]', password);
                await click('ak-stage-password >> button[type="submit"]');
                await authenticatedRedirect("passkey-browser-fixture", returnTarget);
                await until(() => evaluate(`location.pathname + location.search === ${JSON.stringify(returnTarget)}`), "original target remains immutable");
            });
            await test("native flow: fallback flags cannot bypass password or incomplete MFA", async () => {
                await reset({ mode: "cancel" });
                await navigate(fallbackPath + "&auth_method=auth_webauthn_pwl&passkey_success=true");
                await fill('input[name="uidField"]', "passkey-browser-fixture");
                await click('button[type="submit"]');
                await fill('ak-stage-password >> input[name="password"]', "intentionally-wrong-fixture-password");
                await click('ak-stage-password >> button[type="submit"]');
                await until(() => state.components.filter(c => c === "ak-stage-password").length >= 2, "wrong password rejected");
                assert.equal(await authenticated(), false);
                await fill('ak-stage-password >> input[name="password"]', password);
                await click('ak-stage-password >> button[type="submit"]');
                await until(() => state.getRequests > 0, "fallback MFA attempted");
                assert.ok(state.components.includes("ak-stage-authenticator-validate"));
                assert.equal(await authenticated(), false, "Cancelled fallback MFA must not create a session");
            });
            await test("native flow: invalid signature cannot skip fallback", () => rejectAssertion("invalid", {}, undefined, entry));
            await test("native flow: unknown credential is rejected", () => rejectAssertion("unknown", {}, undefined, entry));
            await test("native flow: replayed assertion is rejected", () => rejectAssertion("replay", { replay }, undefined, entry));
            await test("native flow: insufficient UV cannot skip fallback", () => rejectAssertion("valid", {}, { isBadUV: true }, entry));
            await test("native flow: an external initial return target stays on the fixture origin", async () => {
                await reset();
                await navigate("/flows/-/default/authentication/?next=" + encodeURIComponent("https://example.invalid/"));
                await authenticatedRedirect("passkey-browser-fixture", "/if/user/");
                await until(() => evaluate(`location.origin === ${JSON.stringify(base)} && location.pathname === '/if/user/'`), "unsafe target replaced by local default");
            });
        }
    }
} catch {
    console.log("FAIL: browser fixture infrastructure");
    failures++;
} finally {
    if (failures) process.exitCode = 1;
    for (const request of pending.values()) { clearTimeout(request.timer); request.reject(new Error("Browser closing")); }
    pending.clear();
    chrome.kill("SIGTERM");
    await new Promise(resolve => { if (chrome.exitCode !== null || chrome.signalCode !== null) resolve(); else chrome.once("exit", resolve); });
    await rm(profile, { recursive: true, force: true });
}
