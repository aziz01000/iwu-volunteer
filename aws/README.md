# AWS deployment notes for VolunteerBridge AI

This application is a FastAPI service with a local SQLite database. The files in this folder are prepared for a container-based AWS deployment path, but no AWS resources were created here.

## Recommended deployment path

Use AWS App Runner with a container image from Amazon ECR:

1. Build the Docker image locally.
2. Push it to ECR.
3. Create an App Runner service from that image.
4. Set environment variables for runtime config.
5. Keep the database on a persistent file volume or migrate to a managed database for production.

## Important production caveat

The current app stores session data and the application database in SQLite at data/app.db. SQLite is acceptable for a local demo or lightweight testing environment, but it is not a durable production database for multiple app instances or autoscaling.

For a true production deployment, replace SQLite with PostgreSQL or MySQL and update the app configuration to use a hosted database.

## Suggested runtime env vars

- PORT
- DATABASE_PATH
- OPENAI_API_KEY
- AI_API_KEY
- APP_ENV

## Example local build

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker build -t volunteerbridge:latest .
docker tag volunteerbridge:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/volunteerbridge:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/volunteerbridge:latest
```

Then create an App Runner service using the pushed image.
