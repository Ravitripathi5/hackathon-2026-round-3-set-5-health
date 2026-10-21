# Start Here — Round 3 Set 5: Service Health Monitor

This is an individual 90-minute Build & Break challenge. Do not start until the organizer tells you to begin.

## Before the clock starts

You need:

1. Participant ID, such as `p07`
2. Private credential file, such as `h3-p07.env`
3. This repository or its participant ZIP
4. Submission location and deadline

Confirm these commands work:

```bash
git --version
python3 --version
terraform version
aws --version
docker version
```

Docker Desktop or Colima must be running. If you use another Docker-compatible engine, confirm the `docker` commands below work before the event.

## 1 — Open your set

Git:

```bash
git clone https://github.com/Ravitripathi5/hackathon-2026-round-3-set-5-health.git
cd hackathon-2026-round-3-set-5-health
```

ZIP: extract the organizer's ZIP, enter the extracted folder, and confirm it contains `set.json`.

Work locally. Do not push your completed solution to the public repository.

## 2 — Read in this order

1. `START-HERE.md`
2. `RULES.md`
3. `BRIEF.md`
4. `FINDINGS.md`

`BRIEF.md` is the source of truth for exact names, settings, and behavior.

## 3 — Load and verify credentials

Use the actual location of the private file:

```bash
source /path/to/h3-p07.env
export AWS_REGION=ap-south-1
export AWS_DEFAULT_REGION=ap-south-1
aws sts get-caller-identity
```

Stop and ask the organizer if the ARN does not show your assigned `h3-pXX` IAM user or the expected event account. Never copy this credential file into the work folder.

## 4 — Prepare Terraform

```bash
cp infra/terraform.tfvars.example infra/terraform.tfvars
```

Set:

- `participant_id` to the value of `PARTICIPANT_ID`
- `permissions_boundary_arn` to the complete value of `PERMISSIONS_BOUNDARY_ARN`
- `set_name` to `health`

`infra/providers.tf` already defines `local.prefix`; do not define it again. Use `local.prefix` from that file. Every IAM role must include:

```hcl
permissions_boundary = var.permissions_boundary_arn
```

## 5 — Test the supplied application

```bash
python3 -m unittest discover -s app
```

## 6 — Complete Part A: Build

Write:

- Root `Dockerfile` using `public.ecr.aws/lambda/python:3.12`
- Complete Terraform in `infra/`
- Root `.github/workflows/deploy.yml`

The Dockerfile must copy the supplied application, use `handler.lambda_handler`, run on Lambda, and bake the `APP_VERSION` build argument.

Validate Terraform:

```bash
terraform -chdir=infra init
terraform -chdir=infra fmt
terraform -chdir=infra fmt -check
terraform -chdir=infra validate
```

### ECR-first deployment sequence

The Lambda cannot be created until its image exists. Use this order after adding an ECR resource named `aws_ecr_repository.app` (replace that target only if you chose another Terraform label):

```bash
terraform -chdir=infra apply -target=aws_ecr_repository.app

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.ap-south-1.amazonaws.com"
REPOSITORY="h3-${PARTICIPANT_ID}-health"

aws ecr get-login-password --region ap-south-1 \
  | docker login --username AWS --password-stdin "${REGISTRY}"

docker build --platform linux/arm64 --provenance=false \
  --build-arg APP_VERSION=v1 \
  -t "${REGISTRY}/${REPOSITORY}:v1" .
docker push "${REGISTRY}/${REPOSITORY}:v1"

terraform -chdir=infra plan
terraform -chdir=infra apply
```

The `v1` tag is immutable. If you pushed the wrong image, delete that image before pushing a corrected `v1`:

```bash
aws ecr batch-delete-image \
  --repository-name "h3-${PARTICIPANT_ID}-health" \
  --image-ids imageTag=v1
```

The CI file is graded as a submitted file. It must run tests, use GitHub OIDC, build/push ECR, and run Terraform fmt, validate, and plan. Do not push it to the public challenge repository.

Run the live checker:

```bash
python3 tools/check_build.py --id "$PARTICIPANT_ID"
```

Fix every failed item you can. Resource names must match `BRIEF.md`, the region is only `ap-south-1`, and nothing in `crack-files/` should be deployed.

## 7 — Complete Part B: Break

`crack-files/` is an unsafe teammate pull request with six planted issues.

For each issue:

1. Locate it.
2. Fix it in place; deleting the file does not count.
3. Keep the file meaningful.
4. Add a `FINDINGS.md` row with location, vulnerability, impact, remediation, and why the fix works.

Review secrets, exposure, IAM/trust, containers or workloads, CI/CD, and application code.

## 8 — Complete Part C: Operate

- Keep credentials, `terraform.tfvars`, state, and caches out of the submission.
- Keep the required default tags.
- Answer every operations question in `FINDINGS.md`.
- Leave deployed resources running for grading.

## 9 — Submit

```bash
python3 tools/submit.py --id "$PARTICIPANT_ID"
```

Upload `set-5-${PARTICIPANT_ID}-submission.zip` to the organizer's location. Do not run `terraform destroy`; the organizer grades first and cleans up afterward.

## Suggested 90-minute plan

- Minutes 0–5: identity, rules, brief, variables
- Minutes 5–55: Part A build, deploy, and live checker
- Minutes 55–85: Part B six fixes and `FINDINGS.md`
- Minutes 85–90: Part C answers, package, and upload

If deployment blocks you for 15 minutes, move to Part B and return later.

## Separate exercises

The MCQ and pipeline lab are separate. The organizer supplies them separately if scheduled. Their answers are not in this repository.

## Final checklist

- Unit tests pass.
- Terraform fmt and validate pass.
- The live checker was run.
- Six security issues are fixed and documented.
- Operations questions are answered.
- The submission ZIP is uploaded on time.
- AWS resources remain available for grading.
