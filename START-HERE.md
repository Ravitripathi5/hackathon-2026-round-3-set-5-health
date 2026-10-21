# Start Here — Round 3 Set: Health

This is an individual 90-minute Build & Break challenge. Do not start until the organizer tells you to begin.

## What the organizer gives you

You need all four items before the clock starts:

1. Participant ID, such as `p07`
2. Private credential file, such as `h3-p07.env`
3. This repository URL
4. Submission/upload location and deadline

The credential file is private. Never copy it into this repository or send it to anyone.

## Tools required

Confirm these commands work before the event:

```bash
git --version
python3 --version
terraform version
aws --version
docker version
```

Docker Desktop, Colima, or Podman must be running.

## Step 1 — Clone and enter your set

```bash
git clone https://github.com/Ravitripathi5/hackathon-2026-round-3-set-5-health.git
cd hackathon-2026-round-3-set-5-health
```

Work locally. Do not push your completed solution to this public repository.

## Step 2 — Read before changing files

Read in this order:

1. `START-HERE.md`
2. `RULES.md`
3. `BRIEF.md`
4. `FINDINGS.md`

`BRIEF.md` is the source of truth for exact resource names and behaviour. The grader checks those names exactly.

## Step 3 — Load and verify your AWS identity

Replace the filename with the one supplied by the organizer:

```bash
set -a
source ~/Downloads/h3-p07.env
set +a

export AWS_REGION=ap-south-1
export AWS_DEFAULT_REGION=ap-south-1
aws sts get-caller-identity
```

Stop and ask the organizer if the identity does not show your assigned `h3-pXX` IAM user or the event sandbox account.

## Step 4 — Prepare Terraform variables

```bash
cp infra/terraform.tfvars.example infra/terraform.tfvars
```

Edit `infra/terraform.tfvars`:

- Replace `pXX` with your participant ID.
- Replace the example boundary ARN with `PERMISSIONS_BOUNDARY_ARN` from your credential file.
- Keep the supplied set name `health`.

Every IAM role you create must contain:

```hcl
permissions_boundary = var.permissions_boundary_arn
```

Use a prefix without a trailing hyphen:

```hcl
locals {
  prefix = "h3-${var.participant_id}"
}
```

For participant `p07`, a resource described as `${local.prefix}-health` is `h3-p07-health`, not a name with two hyphens.

## Step 5 — Run the provided tests

```bash
python3 -m unittest discover -s app
```

The provided application must pass before you package it.

## Step 6 — Complete Part A: Build (50 points)

Use `BRIEF.md` as your checklist:

1. Write the root `Dockerfile` for the supplied Lambda handler.
2. Build for `linux/arm64`; with BuildKit use `--provenance=false`.
3. Complete the Terraform TODOs in `infra/`.
4. Create the ECR repository first.
5. Log in to ECR and push image tag `v1`.
6. Apply the remaining Terraform resources.
7. Create `.github/workflows/deploy.yml` with tests, AWS OIDC, ECR build/push, and Terraform fmt/validate/plan. It is checked as a file; do not push it to this public repo.
8. Run the supplied live checker.

Local Terraform checks:

```bash
terraform -chdir=infra init
terraform -chdir=infra fmt
terraform -chdir=infra fmt -check
terraform -chdir=infra validate
terraform -chdir=infra plan
```

Live checker:

```bash
python3 tools/check_build.py --id p07
```

Replace `p07` with your ID. Read every failed check, fix the resource or behaviour, and run the checker again.

Important:

- Resource names start with `h3-<your-id>-`.
- Region is only `ap-south-1`.
- ECR tag `v1` is immutable. Plan your image before pushing it.
- Do not hardcode credentials or the AWS account ID.
- Do not deploy anything from `crack-files/`.

## Step 7 — Complete Part B: Break (40 points)

`crack-files/` is a teammate's unsafe pull request. It contains six planted security issues.

For each issue:

1. Locate it.
2. Fix it in place; deleting the file does not count.
3. Keep the file meaningful and usable.
4. Add a row to `FINDINGS.md` explaining the file/location, vulnerability, impact, remediation, and why the fix works.

Review secrets, exposure, IAM/trust, containers, CI/CD, and application code. Do not ask the organizer to confirm a finding; organizers may help only with setup.

## Step 8 — Complete Part C: Operate (10 points)

Before submission:

- Keep credentials and Terraform state out of the work folder/ZIP.
- Keep required resource tags.
- Answer all operations questions in `FINDINGS.md`.
- Submit on time.
- Leave AWS resources running so the organizer can grade them.

## Step 9 — Submit

```bash
python3 tools/submit.py --id p07
```

Replace `p07` with your ID. Upload the generated ZIP to the organizer's submission location. Do not manually add your credential file, Terraform state, or cache directories.

Do not run `terraform destroy`. The organizer performs live grading first and cleans the account afterward.

## Suggested 90-minute plan

- Minutes 0–5: identity, rules, brief, variables
- Minutes 5–15: tests, Dockerfile, Terraform structure
- Minutes 15–40: ECR, image and infrastructure
- Minutes 40–55: live checker and deployment corrections
- Minutes 55–82: six security fixes and `FINDINGS.md`
- Minutes 82–87: operations answers and final checks
- Minutes 87–90: create and upload submission

If deployment blocks you for more than about 15 minutes, move to Part B and return later. Part B is worth 40 points.

## Quiz and pipeline exercise

The MCQ and pipeline lab are separate from this set. If the organizer schedules them:

- The organizer supplies a separate quiz form or question sheet. Choose one option per question and submit before that quiz deadline.
- The organizer supplies a separate `pipeline-lab/` folder and its instructions.
- MCQ answers and pipeline solutions are not present in this public repository.

## What help is allowed

You may use official AWS, Terraform, Docker, GitHub Actions, and Python documentation. The organizer may help with missing tools, Docker startup, credential loading, region, provider downloads, and permissions-boundary setup.

The organizer cannot identify security issues, write code or Terraform, fix your pipeline, or run the deployment for you. Follow `RULES.md` for the complete policy.

## Final checklist

You are finished only when:

- Unit tests pass.
- Terraform fmt and validate pass.
- The live checker has been run and you understand any remaining failures.
- Six security issues are fixed and documented.
- Operations questions are answered.
- Submission ZIP is uploaded before the deadline.
- AWS resources remain available for grading.