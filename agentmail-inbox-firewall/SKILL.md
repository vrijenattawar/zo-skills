---
name: agentmail-inbox-firewall
description: Hardened AgentMail webhook receiver operations for multi-inbox routing, security triage, and service deployment.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
created: 2026-02-16
last_edited: 2026-02-16
version: 1.0
provenance: con_qkaSQZCvQoQlHBTn
---

# AgentMail Inbox Firewall

Use this skill to run and validate the AgentMail receiver in `N5/services/agentmail_webhook`.

## Commands

Run from workspace root:

```bash
python3 Skills/agentmail-inbox-firewall/scripts/agentmail_firewall.py validate
python3 Skills/agentmail-inbox-firewall/scripts/agentmail_firewall.py bootstrap
python3 Skills/agentmail-inbox-firewall/scripts/agentmail_firewall.py test
python3 Skills/agentmail-inbox-firewall/scripts/agentmail_firewall.py run --host 0.0.0.0 --port 8791
python3 Skills/agentmail-inbox-firewall/scripts/agentmail_firewall.py service-spec --port 8791
```

## Required Env Vars (production)

- `AGENTMAIL_WEBHOOK_SECRET` (must start with `whsec_`)
- `AGENTMAIL_INBOX_ROLE_MAP` (optional JSON map)
- `AGENTMAIL_TRUSTED_SENDERS` (optional comma-separated)
- `AGENTMAIL_TRUSTED_SENDER_DOMAINS` (optional comma-separated)

## Behavior

- Verifies config and bootstrap paths
- Runs security tests + signed webhook verification
- Emits service registration spec for Zo hosted services
