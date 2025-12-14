#!/bin/bash

echo "Starting Discord Trading Bot with Docker Compose..."
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Please create one from .env.example"
    echo ""
fi

# Start services
docker-compose up -d

echo ""
echo "Discord trading bot started!"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose down"
