#!/usr/bin/env sh
set -eu

for required in MINIO_ROOT_USER MINIO_ROOT_PASSWORD MINIO_APP_ACCESS_KEY MINIO_APP_SECRET_KEY MINIO_BUCKET; do
  eval "value=\${$required:-}"
  if [ -z "$value" ]; then
    echo "$required must not be empty" >&2
    exit 2
  fi
done

mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing "local/$MINIO_BUCKET"

# Existing demo deployments may intentionally use the root credentials as a
# compatibility fallback.  New/production deployments must set distinct APP
# credentials, in which case only the bucket-scoped policy is granted.
if [ "$MINIO_APP_ACCESS_KEY" = "$MINIO_ROOT_USER" ]; then
  echo "WARNING: MinIO application account equals root; set distinct MINIO_APP_* credentials." >&2
  exit 0
fi

policy_file=/tmp/smartreview-policy.json
cat > "$policy_file" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": ["arn:aws:s3:::$MINIO_BUCKET"]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"],
      "Resource": ["arn:aws:s3:::$MINIO_BUCKET/*"]
    }
  ]
}
EOF

mc admin user add local "$MINIO_APP_ACCESS_KEY" "$MINIO_APP_SECRET_KEY"
mc admin policy create local smartreview-bucket-access "$policy_file"
mc admin policy attach local smartreview-bucket-access --user "$MINIO_APP_ACCESS_KEY"

echo "MinIO bucket-scoped application account is ready."
