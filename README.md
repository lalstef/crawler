# Requirements
Install `docker` and `docker-compose`. Start `docker` daemon.

# Environment variables
Set the following environment variables:

```
export POSTGRES_USER="<database_user>"
export POSTGRES_PASSWORD="<database_password"
export POSTGRES_DB="<database_name>"
export POSTGRES_DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}"
```

# Run

```
cd crawler
./run.sh
```