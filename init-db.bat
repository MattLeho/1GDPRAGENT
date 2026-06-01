@echo off
echo Applying database schema...
docker exec -i gdpr_postgres psql -U admin -d gdpr_local < "02_DATABASE_SCHEMA.sql"
if %ERRORLEVEL% EQU 0 (
    echo Schema applied successfully.
) else (
    echo Failed to apply schema.
)
pause
