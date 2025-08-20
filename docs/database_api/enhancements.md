# Enhancements

| id | status | enhancement | description |
| - | - | - | - |
| 01 | open | public API KEY Auth | open to public and authenticate using JWT API key |

## (open) 01 public API KEY Auth

__situation__
Current release security is enforced at the network level.  traffic is not allowed from public, restricts to private VPC. Future release would be more flexible to allow intergration with other 3rd party services and apps and would need public + API authentication.

__requirements__

**Allowlist**: Check x-api-key against hashed allowlist in config or environment.

Auth decision flow (short):

- If settings.auth.mode == "none" ⇒ allow.
- If "jwt" ⇒ verify signature/claims; inject principal into request context.
- If "key" ⇒ verify HMAC or constant-time compare.

Route-level allow/deny via policies.json (e.g., block DELETE in prod).
No “login” endpoint in prod. For dev only, an optional /auth/dev-token can issue short-lived HMAC tokens if enabled in policies (off by default).