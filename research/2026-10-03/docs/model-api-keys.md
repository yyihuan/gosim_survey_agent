# Participant model API keys for formal runs

Formal runs never use organizer model credits. "Formal" means every run for which
`private.observer_personal_models_only()` is true: runs in a phase that counts for
the final ranking or has the slug `online`, and every run (including model-assisted
project preparation) while the site is in competition mode. Other runs, such as
the practice/acceptance paths outside competition mode, keep their existing
behaviour. Deterministic projects need no API.

Each team chooses in the workspace section **Model API (optional)**:

| | Do not save (default, page relay) | Save encrypted (opt-in) |
|---|---|---|
| Key location | only the open page's memory | AES-GCM ciphertext in `private.observer_providers` |
| Page must stay open | yes, until each evaluation finishes; also at the time agreed for top-team verification | no |
| Deleted | when the page closes | automatically after the results are verified (see "Automatic deletion"), or by the team at any time |
| Call path | model proxy → Broadcast → open page → portal → provider | model proxy calls the provider directly |
| Per-run bounds | phase settings: 100,000 calls, up to 4 at a time; tokens not metered | phase settings: 100,000 calls, up to 4 at a time; tokens 1,000,000,000 (effectively uncapped) |
| Size caps | 64 KiB request, 192 KiB response | 64 KiB request, 192 KiB response |

Not saving is the default: a team that has not chosen is in relay mode
(`20260926000600_model_key_opt_in_auto_purge`; teams that already chose stored
mode or saved a key keep it). The workspace lists "Do not save (default)" first
and selected, with one sentence on the trade-off (e.g. "Not saved: keep this page
open during evaluations. Saved: stored encrypted and deleted automatically after
the results are verified."). Saving on the server is an explicit opt-in: choosing
"Save encrypted on the server" (`observer_set_team_model_mode('stored')`) or
saving a key selects stored mode. Choosing "Do not save" deletes a saved key
immediately (`observer_set_team_model_mode('relay')`, same transaction). Only team
members (not banned) can change the choice or manage the key; it is team-wide.

## Stored mode (opt-in)

1. After opting in, a member enters any public HTTPS endpoint (see "Which endpoints are accepted"
   below), the model and the key, and saves (`save_team_model` portal action,
   over HTTPS). The portal checks the endpoint, creates a new provider ID and
   encrypts the key with the Edge
   application key `OBSERVER_KEY_ENCRYPTION_KEY` (AES-GCM, provider ID as
   additional data). Only the ciphertext and, for keys of at least 16 characters,
   the last four characters as a recognition hint reach the database
   (`observer_save_team_model`, service role only). One key per team; saving
   again replaces it and wipes the previous ciphertext.
2. Clients only ever receive `{mode, saved: {base_url, model, key_hint, saved_at}}`.
   No API returns the key or ciphertext.
3. The project keeps using the scoped `OPENAI_BASE_URL`/`OPENAI_API_KEY` of its
   run. `observer_model_route` answers `{personal: true, mode: "stored"}` and the
   proxy reserves the call with `observer_reserve_team_model`. It checks the run
   capability and deadline, the per-run call/token limits and at most
   `model_concurrency` outstanding calls, and returns only the run team's own
   saved provider. Without a saved key the call fails with `team_model_not_configured` (HTTP 403). No organizer,
   shared, legacy or other-team provider is ever substituted; the
   `a_disallow_stored_formal_model` trigger on `private.observer_model_calls`
   enforces this again for every call receipt.
4. The Edge function re-checks the base with the endpoint rule below (including
   a fresh DNS lookup), decrypts the key in request memory only,
   sends one non-streaming request with `redirect: "error"` using the saved model
   name (the project's `model` value is replaced), redacts the key from the
   response and drops its reference. Usage reported by the provider is settled;
   unknown usage is charged at the reserved upper bound.
5. Provider bodies, headers, redirects and exception text are never forwarded;
   the project receives only an error code.

The key never enters project containers, job payloads or Actions inputs (projects
receive only their scoped run credential), run artifacts, logs, audit-log details
(team, user and base URL only) or error messages.

`observer_delete_team_model` (and choosing relay mode) wipes the key at once. A
provider row referenced by call receipts keeps only non-secret metadata (base URL,
model name) with an empty `encrypted_key`; unreferenced rows are deleted. Calls
already in flight may finish. A team that saved a key but never made a call must
delete the key before it can be disbanded (the row references the team).

## Relay mode ("Do not save", default)

Unchanged ephemeral flow. The participant selects a supported HTTPS base, model
and key in the workspace; they stay in Vue memory without browser storage. Each
active run gets an unguessable Broadcast channel, readable only by the owning
team. The proxy reserves a call ID and broadcasts the prompt; the open page
submits it with the key to the authenticated portal, which verifies team
ownership and the exact prompt digest, claims the call once and calls the
page's endpoint only if it passes the endpoint rule below, with redirects disabled. The database stores the channel
and call receipts, never the key, ciphertext, prompt or response. Without an
attached page the call fails within the bounded wait; there is no organizer
fallback. The relay functions refuse teams in stored mode
(`personal_model_not_enabled`; `observer_personal_model_routes` returns no
routes). Do not use SQL `realtime.send()` for this relay: database Broadcast
persists messages (https://supabase.com/docs/guides/realtime/broadcast).
The relay uses the run's `model_call_limit` and `model_concurrency` (a call
counts as outstanding for at most 150 seconds); tokens are not metered.

If a relay-mode team is verified as a top team after the competition, its page
must be open at the time agreed with the organizers so the re-run can call its
model.

## Organizer steps

Deploy in this order: `scripts/deploy-observer-backend.py --apply` (migrations
`20260926000200_stored_model_keys` and `20260926000600_model_key_opt_in_auto_purge`;
the script applies every migration from `20260925000100` onward and records each
hash), then the Edge functions `observer-model` and `observer-portal`, then the
website. Formal model calls fail closed in between.

`OBSERVER_MODEL_BASES` (exact bases, comma-separated, written by
`scripts/configure-observer-secrets.py`) is no longer an allowlist for teams. Its
HTTPS entries are shown as suggestions in the workspace and are trusted as they
are (the local test stacks rely on this for their loopback stubs). Its HTTP
entries are never usable for team keys.

## Which endpoints are accepted

Teams are not limited to a provider list. The same rule applies to saved keys
(when saving and again before every call) and to the page relay
(`_shared/observer-public-base.ts`):

- `https://` only, default port 443, no user name or password, no query or
  fragment; a trailing slash is dropped.
- The host must be a DNS name with at least one dot. IP literals (in any
  spelling) are refused, as are `localhost` and names under `.localhost`,
  `.local`, `.internal`, `.intranet`, `.lan`, `.home.arpa`, `.arpa`, `.test`,
  `.example`, `.invalid` and `.onion`.
- The name is resolved (A and AAAA) and every address must be public unicast.
  Refused: 0/8, 10/8, 100.64/10, 127/8, 169.254/16, 172.16/12, 192.0.0/24,
  192.0.2/24, 192.88.99/24, 192.168/16, 198.18/15, 198.51.100/24,
  203.0.113/24, 224/4 and above, and every IPv6 address outside 2000::/3 or in
  2001:db8::/32, 2001::/23 or 2002::/16 (this covers ::1, IPv4-mapped, NAT64,
  ULA fc00::/7, link-local and multicast). A name without any record is
  refused. If the runtime offers no working DNS lookup, the naming rules still
  apply.
- Redirects are never followed, and TLS certificate checks bind each connection
  to the name. A name that later resolves to an internal address therefore
  still cannot reach an internal HTTPS service, and internal plain-HTTP services
  are out of reach because HTTP is refused.

A refused endpoint returns `model_destination_not_enabled` when saving, and
`provider_not_authorized` for a call.

Phases whose runs use the team's own key (formal `online` and final phases,
`practice-projects`, internal `observer-acceptance-*`) get these per-run model
limits in `public.observer_phase_settings`: `model_call_limit` 100,000,
`model_token_limit` 1,000,000,000 (effectively uncapped; the team pays for its
tokens) and `model_concurrency` 4. Every call still passes through the
`observer-model` Edge function, so calls stay capped. Migration
`20260926000700_participant_model_limits.sql` sets them for existing phases;
`configure-observer-competition.py`, `configure-observer-practice-projects.py`
and `configure-observer-acceptance.py` use them for new ones. Phases that use
organizer keys are unchanged. Runs opened earlier keep the limits they started
with.

### Automatic deletion

No organizer step is needed. Where pg_cron is available (the hosted database),
the job `observer-purge-provider-keys` runs `private.observer_auto_purge_provider_keys()`
every hour (at minute 17). It wipes every participant-owned key of a team
(saved team keys and keys retained from the former provider settings) with the
same `private.observer_forget_provider_key` as the manual purge, once **all** of
these hold:

1. **No phase that can use the key is open or upcoming.** The phases that can
   use a team's key are the active phases whose runs are formal
   (`private.observer_personal_models_only`): `counts_for_final`, slug `online`,
   `observer-acceptance-*` and `practice-projects`; while the site is in
   competition mode, also every other active phase with
   `observer_phase_settings`. A phase restricted to another team
   (`access_team_id`) is ignored. Every such phase must have an `ends_at`, and
   the latest one must have ended at least the retention period ago. An
   open-ended phase (`ends_at` null) keeps the key.
2. **The key was saved at least the retention period ago.**
3. **Nothing of the team is in progress:** no queued/starting/ready/running run,
   no queued/running batch, no queued/preparing project revision and no
   unsettled model-call reservation on its keys.

Why this rule: the schema has no "results verified" flag, so the end of the last
phase that can use the key plus a retention period (default **7 days**) stands in
for the verification window, including re-runs of top teams. Condition 3 means a
key is never deleted under a running or queued evaluation. The check takes the
team row lock, as saving and deleting a key do.

The team's mode is left as it is; the workspace then shows stored mode without a
saved key, and the team can save again or choose "Do not save". Each run that
deletes keys writes an `observer.provider_keys_auto_purged` audit entry with the
count and team IDs (never key material).

Settings (service role), in `private.observer_key_retention`:

```sql
update private.observer_key_retention set retention = interval '14 days' where id;  -- longer verification
update private.observer_key_retention set enabled = false where id;                  -- pause
select * from private.observer_key_retention;  -- last_run_at shows the last check
```

Without pg_cron (plain PostgreSQL, e.g. the tests) the function is installed but
not scheduled; call `select private.observer_auto_purge_provider_keys();` from
any scheduler.

### Manual purge

To delete every participant key at once, regardless of phases, run with the
service role, for example in the SQL editor or management SQL API:

```sql
select public.observer_purge_provider_keys();  -- returns the number of keys deleted
select count(*) from private.observer_providers
  where team_id is not null and encrypted_key <> '';  -- expect 0
```

or `POST /rest/v1/rpc/observer_purge_provider_keys` with the service-role key.
It wipes every participant-owned key (saved team keys and keys retained from the
former provider settings), removes the saved-key records and writes an
`observer.provider_keys_purged` audit entry with the count. Organizer providers
(`team_id is null`) are untouched and call receipts remain. It is idempotent and
returns 0 when nothing is left. Unlike the automatic deletion it does not wait
for evaluations in progress (calls already in flight may finish).

## Validation

- `tests/test_personal_models.py` (real PostgreSQL): relay is the default and the
  opt-in migration keeps teams that saved (and is idempotent), save, replace,
  delete, team isolation, no key or ciphertext in any participant-visible result,
  stored-mode reservations use only the team's own key, no organizer fallback in
  either mode, choosing relay deletes the key, relay claims and receipts,
  `model_concurrency` outstanding calls and per-run limits in both modes, manual
  purge, automatic deletion (open, upcoming and recently ended phases, retention
  after saving, other-team and competition-mode phases, queued runs and unsettled
  calls keep the key; pause switch; audit), and the migrations' limit updates.
- `web/tests/modelKeyMode.test.ts`: the workspace defaults to "Do not save" and
  every locale explains the trade-off.
- `observer-model_test.ts`, `observer-portal_test.ts`: HTTPS/approved-host and
  redirect rules, decryption per request, redaction, response cap, no fallback,
  encryption before storage. `observer-personal-model_test.ts`: relay behaviour.
- `tests/test_project_http.py`: real Deno Edge functions, PostgREST and an HTTPS
  stub provider trusted through a throwaway test CA: a formal run calls the saved
  provider with the saved key and model, redirects and provider errors are not
  forwarded, deleting the key stops use, relay mode fails closed without any
  server-side call, and the plaintext key appears in no table or Edge log.
- `tests/test_project_portal_browser.py`: default relay mode with the trade-off
  sentence, opt in and save with masked hint, switch to relay (key deleted),
  relay key not kept in browser storage, opt in again, headings in all four
  languages.
- Opt-in: `integration/deployed-personal-model.ts` (selects relay mode first,
  which deletes that team's saved key) and `integration/personal-broadcast_test.ts`.

A live check with a real provider through the deployed proxy is still required
before relying on either mode; these tests use stubs and synthetic keys.
