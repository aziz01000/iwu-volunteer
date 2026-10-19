#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID before running this script}"
ECR_REPO="${ECR_REPO:-volunteerbridge}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
SERVICE_NAME="${SERVICE_NAME:-volunteerbridge-service}"

aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$AWS_REGION" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "$ECR_REPO" --region "$AWS_REGION" >/dev/null

aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker build -t "${ECR_REPO}:${IMAGE_TAG}" .
docker tag "${ECR_REPO}:${IMAGE_TAG}" "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"
docker push "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"

echo "Image pushed to ECR. Create the App Runner service manually or with:
aws apprunner create-service \
  --cli-input-json '{
    "ServiceName": "${SERVICE_NAME}",
    "SourceConfiguration": {
      "ImageRepository": {
        "ImageIdentifier": "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}",
        "ImageRepositoryType": "ECR",
        "ImageConfiguration": {
          "Port": "8000",
          "RuntimeEnvironmentVariables": {
            "PORT": "8000",
            "DATABASE_PATH": "/app/data/app.db",
            "APP_ENV": "production"
          }
        }
      }
    },
    "InstanceConfiguration": {
      "Cpu": "1024",
      "Memory": "2048"
    }
  }'
"
