---
description: This file describes the Ansible instructions for the project.
applyTo: src/**/*.yml
---

# Ansible Instructions

- Use modern Ansible practices, such as using `ansible.builtin` modules and avoiding deprecated features.
- Ensure that all playbooks and roles are idempotent and can be safely re-run without causing unintended side effects.
- Follow the Ansible best practices for directory structure and naming conventions to maintain consistency across the project.
- Use Ansible Vault to encrypt sensitive data, such as passwords and API keys, and avoid hardcoding secrets in playbooks or roles.
- Regularly update Ansible and its dependencies to benefit from the latest features and security patches.
