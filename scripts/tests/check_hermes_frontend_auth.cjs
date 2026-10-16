// Feed the deployed /app/static/workspace.js on stdin. Execute only its API
// helper in a mocked browser, inside the repository's Bubblewrap launcher.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(0, 'utf8');
assert.ok(source.startsWith('async function api('), 'Upstream API helper moved; review before updating this check');
const end = source.indexOf('\n}\n');
assert.ok(end > 0, 'Cannot find the end of the upstream API helper');
const helper = source.slice(0, end + 2);

(async () => {
  for (const [path, search, opts, expected] of [
    ['/', '?session=test', {}, 'login?next=%2F%3Fsession%3Dtest'],
    ['/login', '?next=%2F', {}, 'login'],
    ['/', '', {redirect401: false}, 'unchanged'],
  ]) {
    let calls = 0;
    const location = {pathname: path, search, href: 'unchanged'};
    const context = vm.createContext({
      URL,
      window: {location},
      location,
      document: {baseURI: 'https://hermes.example/'},
      fetch: async () => {
        calls++;
        return {ok: false, status: 401};
      },
    });
    vm.runInContext(helper, context, {timeout: 1000});
    context.options = {timeoutMs: 0, ...opts};
    await vm.runInContext('api("/api/projects", options)', context, {timeout: 1000});
    assert.equal(location.href, expected);
    assert.equal(calls, 1, 'Authentication expiry must not trigger network retries');
  }
  console.log('PASS: deployed API helper navigates on 401, avoids login nesting, and respects opt-out (3 cases)');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
