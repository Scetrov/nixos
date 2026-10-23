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
