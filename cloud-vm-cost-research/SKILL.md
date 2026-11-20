---
name: cloud-vm-cost-research
description: Use when comparing cloud VM or hosting costs and data-protection terms across providers, including nonprofit credits and data processing agreements. Research only: no logins, no provisioning.
license: MIT
compatibility: Needs web access and unauthenticated access to public price APIs. Works with any agent that can fetch pages and write files.
---

# Cloud VM cost research

Produce a comparison that someone can check line by line. Every price has a source URL and a retrieval date. Every total says what it includes and what it leaves out. Prices change, so the date matters as much as the number.

## Step 1: Fix the spec

Write the spec before you collect a single price. Each provider gets the same one.

- OS and version (Linux unless the workload needs Windows)
- Region (US, unless the data-residency rules say otherwise)
- vCPU and RAM, and whether the CPU is burstable. A burstable CPU does not provide full cores all the time, so benchmark or price it accordingly.
- Disk type and size, plus snapshot or backup retention in days
- Hours per month the VM runs (730 for always on)
- Public IPv4 count
- Egress estimate in GB per month
- Backup redundancy (local, zone, or region)

## Step 2: Collect list prices

- **Azure.** The retail price API needs no login: `https://prices.azure.com/api/retail/prices`. Filter with `$filter=armRegionName eq '<region>' and armSkuName eq '<sku>' and priceType eq 'Consumption'`. Do not add `not contains(...)` clauses to the filter. The endpoint returns HTTP 400 for them. Exclude Spot, Low Priority, and Windows meters in code after the fetch, by checking `skuName` and `productName`. Pick the non-Windows, non-Spot meter. Save each raw response to a working directory outside the repo. Follow `NextPageLink` until it is empty. The API returns HTTP 429 under load. Back off for 30 to 60 seconds and retry, and say in the ledger that the retry happened.
- **AWS.** Use the pricing pages or the Price List API. Lightsail lists public-IPv4 bundles and IPv6-only bundles separately. Price both.
- **DigitalOcean.** Bundled plans bill up to a monthly cap, so the monthly cost is the cap, not the hourly rate times 730. Its basic daily backup is priced at 30 percent of the Droplet price. Usage-based backup is a separate product priced on restorable data retained. Verify both against the current pricing page before quoting them.
- **Other providers.** Use the pricing calculator or the public price list. If the calculator needs a login or has no export, fetch the page and record the URL.

## Step 3: Price the parts separately

Do not hide costs inside one line item. Price each of these as its own row:

- Compute (VM hours)
- Disk (per GB-month, by type)
- Snapshots and backups. Price retained snapshots as billed GB-months of data retained, not as a full disk times the number of snapshots. Check how the provider deletes old snapshots and whether it keeps the first full copy.
- Public IP
- Protected-instance or vault fees (Azure Site Recovery and Recovery Services vault storage are billed separately from the VM)
- Disk mounts. Shared-disk mounts are not ordinary single-VM attachments and may bill differently.
- I/O transactions, if the provider bills them
- Egress
- Instant-restore or snapshot-tier storage

If a line is excluded from the total, name it. Label an incomplete total as a subtotal.

## Step 4: Data protection

Compare the design, not the VM price.

- **Encryption at rest.** Check each provider's current docs for each storage type. Do not assume every disk is encrypted. DigitalOcean Droplet local disks have been documented as unencrypted at rest. Volumes and object storage follow their own policies. Droplet automatic backups do not include attached Volumes.
- **Data processing agreement.** Read the current DPA, not a summary. Separate these questions: who owns the data, what processing is authorized, what metadata the provider keeps, who at the provider and its subprocessors can access the data, under what legal process data can be disclosed, and where data is stored at rest. A US disk region does not keep processing and support access in the same place.
- **Account control.** Recommend an organization-owned billing account and tenant, recovery contacts with MFA, at least two admins who can recover the account, and revocable delegated access. Cloud IAM roles do not isolate application users from each other.
- **Exit.** Require a tested export of data and configuration before choosing a provider. Proprietary snapshots alone do not make an exit plan.

## Step 5: Nonprofit credits

- Check the program for each provider separately: AWS nonprofit credits, Azure grants, and TechSoup-sourced offers.
- Record the TechSoup tier, its administrative fee, its validity period, its annual request limit, and whether the organization's budget and status qualify for it.
- Track three things separately: the TechSoup tier, any credit-union offer that does not require 501(c)(3) status, and project-specific TechAction grants.
- Confirm that each service in the spec is eligible under the credit, and that the organization owns the domain on the account.
- Eligibility depends on the organization's type and its country. Check both for each program before counting a credit. An approval from one provider does not enroll the organization with another.
- Record validation, activation, renewal, rollover, and excluded services.

## Output

A ledger with one row per price, and a summary table:

| Provider | Spec | Compute/mo | Disk/mo | Backups/mo | IP/mo | Egress est. | Total (includes) | Excludes | Sources |
|---|---|---|---|---|---|---|---|---|---|

Then a data-protection table, one row per provider, with encryption, DPA location, account-control model, and exit path. Then the credit eligibility, with a net-cost line that says which credit was applied and what it does not cover.

## Common errors

- Using the hourly rate times 730 for a plan that has a monthly cap.
- Multiplying a full disk by the number of snapshots.
- Quoting a credit without checking that the specific service is covered.
- Stating an encryption property from memory instead of from the current docs.
