# Why

The operator reported that the Authentik Hermes tile still showed H after the
server's PNG was replaced. Origin-byte verification alone did not establish
that an existing launcher client would refresh its image.

# What Changes

Use a content-addressed Hermes PNG filename and update the application metadata,
Ansible asset list, regression tests, and reproduction documentation.

# Capabilities

## Modified Capabilities

- `authentik-application-icons`: change the icon URL whenever Hermes artwork changes.

# Impact

One application icon metadata update. No changes to SSO, access policy, ports,
service restarts, or other application icons.
