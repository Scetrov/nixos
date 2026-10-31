# FileBrowser Documents Access

This context describes how enrolled people receive browser access to personal Documents stored on Habiki.

## Language

**Enrollment**:
An explicit approval linking an Authentik identity to the Unix account whose Documents the identity may access.
_Avoid_: automatic user provisioning, username matching

**Documents tree**:
The complete `Documents` directory belonging to one Unix account, including its nested contents.
_Avoid_: home directory, files root

**Source**:
A Quantum-accessible file location representing one enrolled user's Documents tree.
_Avoid_: share, scope

**Scope**:
The specific source and path permissions assigned to one Quantum user.
_Avoid_: source, enrollment

**Operator**:
A person explicitly authorized to administer the Quantum service, distinct from an ordinary enrolled user.
_Avoid_: user, member

# Penpot Design Service

This context describes the self-hosted Penpot design service and its remote MCP integration.

## Language

**MCP key**:
The per-user, non-recoverable credential that authenticates one MCP client to the remote MCP server; shown once and revocable by regeneration.
_Avoid_: userToken (except when quoting the URL format), API key, token

**MCP plugin**:
The plugin running inside one Penpot browser tab that connects the currently open file to the MCP server.
_Avoid_: connector, integration

**MCP client**:
The AI tool or agent that connects to the MCP server using the server URL and an MCP key.
_Avoid_: user, browser

**Focused page**:
The Penpot page currently in focus; every MCP operation acts on it.
_Avoid_: current file, active document

**Active MCP tab**:
The single Penpot browser tab that owns the MCP connection at any time.
_Avoid_: session, window
