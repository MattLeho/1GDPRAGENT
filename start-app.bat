@echo off
echo Starting GDPR Local Agent Stack...
docker-compose up -d
echo.
echo Containers are starting...
echo App: http://localhost:3000
echo N8N: http://localhost:5678
echo Database: localhost:5432
echo.
pause
