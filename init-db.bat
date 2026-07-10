@echo off
echo Applying canonical database migrations...
docker compose run --rm migrate
if %ERRORLEVEL% EQU 0 (
    echo Migrations applied successfully.
) else (
    echo Failed to apply migrations.
)
pause
