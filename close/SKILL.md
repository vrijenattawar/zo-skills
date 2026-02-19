---
name: close
description: |
  Universal close skill. Just say "close" and it auto-routes to the right close skill
  (thread-close, drop-close, or build-close) based on SESSION_STATE context.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
---

# Close

Just run the router:

```bash
python3 Skills/thread-close/scripts/router.py --convo-id <CONVO_ID>
```

That's it. The router reads SESSION_STATE and picks the right skill.
