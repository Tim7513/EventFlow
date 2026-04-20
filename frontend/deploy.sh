#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# EventFlow frontend deploy script
#
# Usage:
#   ./frontend/deploy.sh [dev|staging|prod]
#
# What it does:
#   1. Reads CloudFormation outputs to get the API URL and S3 bucket name
#   2. Writes a .env.local with VITE_API_URL set
#   3. Builds the Vite app
#   4. Syncs dist/ to the S3 bucket (with cache headers)
#   5. Invalidates the CloudFront distribution
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ENVIRONMENT="${1:-dev}"
STACK_NAME="eventflow"
if [ "$ENVIRONMENT" != "dev" ]; then
  STACK_NAME="eventflow-${ENVIRONMENT}"
fi

echo "==> Deploying EventFlow frontend (environment: ${ENVIRONMENT}, stack: ${STACK_NAME})"

# ── 1. Read stack outputs ────────────────────────────────────────────────────
echo "==> Fetching CloudFormation outputs..."

API_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text)

BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
  --output text)

DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendUrl'].OutputValue" \
  --output text | sed 's|https://||' | cut -d. -f1)

FRONTEND_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendUrl'].OutputValue" \
  --output text)

# Get distribution ID from domain name (needed for invalidation)
CF_DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?DomainName=='${FRONTEND_URL#https://}'].Id" \
  --output text)

echo "    API URL:         $API_URL"
echo "    S3 Bucket:       $BUCKET"
echo "    CloudFront URL:  $FRONTEND_URL"

# ── 2. Write .env.local ──────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.local"

echo "==> Writing ${ENV_FILE}..."
cat > "$ENV_FILE" <<EOF
VITE_API_URL=${API_URL}
VITE_REFRESH_INTERVAL_MS=5000
EOF

# ── 3. Build ─────────────────────────────────────────────────────────────────
echo "==> Installing dependencies..."
cd "$SCRIPT_DIR"
npm ci --silent

echo "==> Building..."
npm run build

# ── 4. Upload to S3 ──────────────────────────────────────────────────────────
echo "==> Syncing to s3://${BUCKET}..."

# HTML files: no cache (always re-validate)
aws s3 sync dist/ "s3://${BUCKET}/" \
  --exclude "*" \
  --include "*.html" \
  --cache-control "no-cache, no-store, must-revalidate" \
  --delete

# Hashed assets (JS/CSS/images): cache forever — Vite includes content hash in filenames
aws s3 sync dist/ "s3://${BUCKET}/" \
  --exclude "*.html" \
  --cache-control "public, max-age=31536000, immutable" \
  --delete

# ── 5. CloudFront invalidation ───────────────────────────────────────────────
if [ -n "$CF_DIST_ID" ]; then
  echo "==> Invalidating CloudFront distribution ${CF_DIST_ID}..."
  aws cloudfront create-invalidation \
    --distribution-id "$CF_DIST_ID" \
    --paths "/*" \
    --query "Invalidation.Id" \
    --output text
else
  echo "    (skipping invalidation — distribution ID not found)"
fi

echo ""
echo "✓ Frontend deployed to: ${FRONTEND_URL}"
