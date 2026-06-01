#!/bin/bash
echo "Applying database schema..."
docker exec -i gdpr_postgres psql -U admin -d gdpr_local < 02_DATABASE_SCHEMA.sql
if [ $? -eq 0 ]; then
    echo "Schema applied successfully."
else
    echo "Failed to apply schema."
fi
