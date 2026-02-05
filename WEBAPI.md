# Energy Alert Management Web API

A FastAPI-based web application for managing energy data alerts and monitoring solar installation performance.

## Features

- 🌐 **Web Interface**: Responsive dashboard for viewing and managing alerts
- 🔌 **REST API**: Complete RESTful API for programmatic access
- 📊 **Real-time Statistics**: Track pending, sent, and acknowledged alerts
- 🐳 **Docker Support**: Easy deployment with Docker and Docker Compose
- 🔄 **Auto-refresh**: Dashboard updates every 30 seconds
- 📱 **Responsive Design**: Works on desktop, tablet, and mobile

## Quick Start

### Using Docker

Run the Dockerfile

### Running locally (without Docker)

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application:**
   ```bash
   python app.py
   # or
   uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```

## API Documentation

### Endpoints

#### GET `/api/alerts`

Get alerts with optional filtering.

**Query Parameters:**

- `status` (optional): Filter by status (`all`, `pending`, `sent`, `acknowledged`)
- `date` (optional): Filter by date (YYYY-MM-DD)
- `pod_code` (optional): Filter by POD code

**Example:**

```bash
curl "http://localhost:8000/api/alerts?status=pending"
```

#### GET `/api/alerts/stats`

Get alert statistics.

**Example:**

```bash
curl "http://localhost:8000/api/alerts/stats"
```

**Response:**

```json
{
  "total_alerts": 45,
  "pending": 12,
  "sent": 8,
  "acknowledged": 25
}
```

#### POST `/api/alerts/acknowledge`

Acknowledge alerts to prevent them from being sent.

**Query Parameters:**

- `pod_code` (optional): Acknowledge alerts for specific POD
- `date` (optional): Acknowledge alerts for specific date

**Example:**

```bash
# Acknowledge all pending alerts
curl -X POST "http://localhost:8000/api/alerts/acknowledge"

# Acknowledge alerts for specific POD
curl -X POST "http://localhost:8000/api/alerts/acknowledge?pod_code=LU0000010637000000000000070232023"

# Acknowledge alerts for specific date
curl -X POST "http://localhost:8000/api/alerts/acknowledge?date=2025-02-01"
```

#### POST `/api/alerts/reset`

Reset alert flags to allow alerts to be sent again.

**Query Parameters:**

- `pod_code` (optional): Reset alerts for specific POD
- `date` (optional): Reset alerts for specific date

**Example:**

```bash
# Reset all alerts
curl -X POST "http://localhost:8000/api/alerts/reset"

# Reset alerts for specific POD on specific date
curl -X POST "http://localhost:8000/api/alerts/reset?pod_code=LU0000010637000000000000070232023&date=2025-02-01"
```

#### GET `/health`

Health check endpoint.

**Example:**

```bash
curl "http://localhost:8000/health"
```

## Integration Examples

### Python

```python
import requests

# Get all pending alerts
response = requests.get("http://localhost:8000/api/alerts?status=pending")
alerts = response.json()

for alert in alerts:
    print(f"{alert['pod_name']}: {alert['performance_ratio']*100:.1f}%")

# Acknowledge all alerts
response = requests.post("http://localhost:8000/api/alerts/acknowledge")
print(response.json())
```

## Docker Volumes

The application uses a volume mounted at `/data` to persist the database:

```yaml
volumes:
  - ./data:/data
```

Make sure to place your database file in the `./data` directory on the host machine.

## Monitoring

The application includes a health check endpoint:

```bash
curl http://localhost:8000/health
```

Docker will automatically check the health status every 30 seconds.

## Development

### Running in development mode with auto-reload:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Access interactive API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Troubleshooting

### Database not found

- Ensure the database file exists in the `/data` directory
- Check the `DB_PATH` environment variable
- Verify volume mounting in docker-compose.yml

### Port already in use

```bash
# Change the port in docker-compose.yml
ports:
  - "8080:8000"  # Use port 8080 instead
```

### View logs

```bash
# Docker Compose
docker-compose logs -f

# Docker
docker logs -f energy-alert-manager
```

## License

@MarcDurbach 2026

## Support

For issues or questions, please check the API documentation at `/docs` or review the application logs.
