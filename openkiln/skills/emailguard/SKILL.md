# EmailGuard Skill

Inbox placement testing via the EmailGuard API.
Measures whether your emails land in Inbox or Spam across Gmail and Microsoft.

## Provides

This skill provides CLI commands for inbox placement testing.
It does not provide workflow Sources, Transforms, or Sinks.

## Required config
```bash
# Set via environment variable (recommended)
export EMAILGUARD_API_KEY=your-bearer-token

# Or via config file (~/.openkiln/config.toml)
[skills.emailguard]
api_key = "your-bearer-token"
```

Get your API key from https://app.emailguard.io.

## CLI Commands

### create

Create a new inbox placement test. Returns seed email addresses
and a filter phrase to embed in your test email.

```bash
# create with defaults (4 Gmail + 4 Microsoft seeds)
openkiln emailguard create --name "My Test"

# custom seed counts
openkiln emailguard create --name "Gmail Only" --gmail-seeds 8 --msft-seeds 0

# JSON output (for agents)
openkiln emailguard create --name "My Test" --json
```

**Output includes:**
- `test_id` — UUID for checking results later
- `filter_phrase` — unique string to append to your email body
- `seeds` — list of email addresses to send your test email to

### check

Check results of a placement test. Polls EmailGuard and stores
results locally.

```bash
openkiln emailguard check <test_id>
openkiln emailguard check <test_id> --json
```

### report

Generate a formatted report for a placement test.

```bash
openkiln emailguard report <test_id>
openkiln emailguard report <test_id> --json
```

Shows:
- Overall score
- Inbox vs Spam breakdown by provider (Gmail, Microsoft)
- Inbox vs Spam breakdown by sender account
- Individual seed results

### list

List past placement tests.

```bash
openkiln emailguard list
openkiln emailguard list --limit 10
openkiln emailguard list --json
```

## Running a Full Placement Test

A placement test requires two skills: EmailGuard (this skill) and
an outreach skill (e.g. Smartlead) to send the test emails.

### Step-by-step workflow:

**1. Create the test**
```bash
openkiln emailguard create --name "Domain Test - example.com" --json
```

Save the `test_id`, `filter_phrase`, and `seeds` from the output.

**2. Prepare your test email**

Write your email content. Append the `filter_phrase` to the body —
EmailGuard uses this to identify which test the email belongs to.

**3. Send via your outreach skill**

Using Smartlead as an example:

```bash
# create a test campaign
openkiln smartlead create "Placement Test - example.com"

# set the email sequence (with filter phrase in the body)
openkiln smartlead sequence <campaign_id> --file test-email.json

# configure schedule (20min gap for deliverability)
openkiln smartlead schedule <campaign_id> \
  --timezone "US/Eastern" \
  --days 0,1,2,3,4,5,6 \
  --start-hour "00:00" \
  --end-hour "23:59" \
  --min-gap 20

# add your sending accounts
openkiln smartlead accounts add <campaign_id> --account-id <id>

# add the seed addresses as leads
openkiln smartlead push <campaign_id> --apply

# start sending
openkiln smartlead start <campaign_id> --yes
```

**4. Wait for delivery (~2.5-3 hours)**

The seeds need time to receive and process all emails.

**5. Check results**
```bash
openkiln emailguard check <test_id>
openkiln emailguard report <test_id>
```

**6. Clean up**
```bash
openkiln smartlead delete <campaign_id> --yes
```

### Key details:

- **Seed interleaving:** For balanced results across providers, alternate
  Gmail and Microsoft seeds when adding them as leads: G,G,M,M,G,G,M,M.
  This ensures round-robin senders get a mix of both providers.

- **Spacing:** Use 20-minute minimum gaps between sends for realistic
  deliverability conditions.

- **Plain text:** Send as plain text for cleaner placement results.

- **Filter phrase:** Must be in the email body. EmailGuard uses it to
  match incoming emails to the test. Without it, results won't register.
