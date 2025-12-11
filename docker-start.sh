#!/bin/bash

echo "Starting Trading Bot with Docker Compose..."
echo "This will start both the Flask API backend and React frontend"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Please create one from .env.example"
    echo ""
fi

# Start services
docker-compose up -d

echo ""
echo "Services started!"
echo "Frontend: http://localhost:3005"
echo "Backend API: http://localhost:4000"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose down"

