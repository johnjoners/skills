---
name: secure-review
description: Security review for code that touches authentication, authorization, sessions, secrets, cryptography, queries built from user input, untrusted file paths, deserialization, shell execution, network boundaries, or privacy controls such as consent gates and third-party tracker injection. Use when a diff touches auth, login, session, token, secret, crypto, password, or credential files, or when asked for a security review or threat model. Not for UI, styling, or documentation changes.
license: MIT
compatibility: Works with any agent that can read a diff or files and run git commands.
---

# secure-review

A focused security pass on a change, for a small team. The goal is to find what a competent operations engineer would refuse to ship. It is not a compliance audit, and it does not replace one.

## Step 1: Scope the diff

```bash
git diff --stat            # what changed
git diff -- <paths>        # the changed lines
```

If the diff touches only CSS, copy, comments, documentation, or configuration keys that affect neither secrets nor permissions, report `UI/doc-only, no security review needed` and stop.

Flag the change for a full pass if any of these appear: `password`, `token`, `secret`, `api_key`, `session`, `cookie`, `auth`, `login`, `jwt`, `oauth`, `crypto`, `hmac`, `subprocess`, `os.system`, `eval`, `exec`, `pickle`, `yaml.load`, raw SQL string building, `innerHTML`, `dangerouslySetInnerHTML`, `redirect(`, `open(` on a path built from input.

Quick sweep:

```bash
git diff | grep -nE 'password|secret|token|api[_-]?key|eval\(|exec\(|pickle|yaml\.load\(|innerHTML|subprocess|os\.system|verify\s*=\s*False|allow_origins|\*\*kwargs' || echo "no pattern hits"
```

A hit is a lead, not a finding. Read the surrounding code.

## Step 2: Walk the checklist

Answer each question with what the code does, not what it is meant to do.

1. **Access control.** Does every new endpoint or handler check the caller's permission before acting? Is any path reachable without authentication that should not be? Does the check happen on the server, not only in the client?
2. **Least privilege.** Do new service accounts, API scopes, IAM roles, or database grants ask for more than the code uses? Write permission where read would do is a finding.
3. **Secrets.** Any credential in source, in a test fixture, in a config file that is committed, or in a log line? Does an error path print a request body or header that contains a token?
4. **Input validation.** At each trust boundary (HTTP parameters, uploads, CLI arguments, webhook bodies, file names), is the input checked before it reaches SQL, a shell, a filesystem path, a template, or a deserializer?
5. **Output encoding.** Is user-supplied data inserted into HTML, a JavaScript string, a URL, or a shell command without the encoding for that context?
6. **Audit logging.** Does a sensitive action (permission change, data export, credential issue, account deletion) log the actor, the time, and the target? Does the log avoid the secret itself?
7. **Dependencies.** Does the diff add a dependency? Is it maintained, with a release in the last year? Is it pinned?
8. **Errors.** Do error responses expose stack traces, file paths, SQL, or internal hostnames?

## Step 3: Privacy controls

Apply this part when the change touches consent, analytics, tags, or third-party scripts.

- No third-party script or pixel loads before the consent state is known. Test by loading the page with consent unset and checking the network log.
- Rejecting consent prevents the same loads. Test the reject path, not only the accept path.
- The consent value is stored in a way the user can change later, and the change takes effect without a reload if the UI promises that.
- The server does not trust a client-side flag for anything that matters. Check where the value is enforced.
- Tracker injection through a tag manager or a template variable: confirm the value is escaped and that the template cannot be made to load an arbitrary host.

## Step 4: OWASP categories the diff touches

Check only the categories that apply:

- A01 Broken access control
- A02 Cryptographic failures: weak algorithms, reused nonces or IVs, custom crypto, comparison of secrets with `==`
- A03 Injection: SQL, OS command, LDAP, template, and XPath
- A04 Insecure design: missing rate limits, no replay protection, state changes via GET
- A05 Misconfiguration: permissive CORS, debug mode on, default credentials
- A07 Authentication failures: session fixation, long-lived tokens with no rotation, missing lockout on repeated failures
- A08 Integrity failures: unsigned updates, uploads trusted without a check
- A09 Logging failures: secrets in logs, or no record of security events

## Step 5: Escalate, do not approve

Mark `NEEDS-HUMAN` and recommend a specialist before shipping when the change involves:

- A new cryptographic primitive or protocol, or a hand-written one
- SAML, OIDC identity-provider integration, or WebAuthn
- Isolation between tenants
- Regulated data: health (HIPAA), card data (PCI), or student records (FERPA)
- Evidence for a compliance audit

Do not approve these, even when the code looks right.

## Output

For each finding:

```
[BLOCK|NIT|FYI] path/to/file:LINE
  What: <what the code does>
  Why it matters: <the attack or failure>
  Fix: <the smallest change that closes it>
```

- BLOCK: must be fixed before shipping.
- NIT: a reviewer might raise it, but it does not block.
- FYI: worth knowing, no action needed now.

End with one verdict line:

- `SHIP-SECURITY: no security concerns`
- `HOLD-SECURITY: <N> blockers`
- `NEEDS-HUMAN: <reason>`

Do not invent findings to look thorough. If the diff is clean, say so and name what you checked.
