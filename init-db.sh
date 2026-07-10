#!/bin/bash
echo "Applying canonical database migrations..."
docker compose run --rm migrate
if [ $? -eq 0 ]; then
    echo "Migrations applied successfully."
else
    echo "Failed to apply migrations."
fi
