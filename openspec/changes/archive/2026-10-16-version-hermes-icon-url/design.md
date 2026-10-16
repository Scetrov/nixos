# Evidence and Diagnosis Limits

The operator confirmed the old H was on the Authentik tile. The live API still
referenced `/static/dist/branding/hermes.png`, while that origin URL returned
the new PNG. Its headers included `Cache-Control: public, no-transform`, an ETag,
and Last-Modified. The affected user's browser cache was not accessible, so the
exact client-side cause was not reproduced or conclusively established.

# Decision

Replace the reused image URL with `hermes-caduceus-84a4bc433bfd.png`; the suffix
is the first 12 hex digits of the PNG SHA-256. Deploy the asset before applying
the application reference with the mandatory OpenTofu wrapper. A distinct URL
prevents reusing an HTTP image cache entry for the former path. A launcher reload
is still required for existing pages to receive updated application metadata.
The legacy deployed PNG can remain for clients with old launcher data.

# Regression and Verification

The new URL contract test failed against the reused `hermes.png` reference and
passed after the change. This tests cache-safe configuration, not the affected
browser's actual cache state. All five icon tests pass. The live Authentik API
selects the new URL; its PNG matches the repository bytes exactly, and Chrome
loads it at 512 × 512. Final confirmation of the affected tile needs the user's
launcher reload.
