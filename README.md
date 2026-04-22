# SmarTrip - Tourism Assistant AI Microservice

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![License](https://img.shields.io/badge/License-GPL%203.0-blue.svg)

A production-ready Python microservice for AI-powered travel recommendations, user profiling, and traveler matching.

## Description

The SmarTrip Tourism Assistant microservice provides intelligent travel recommendations and companion matching using machine learning algorithms. Built with FastAPI, it offers a scalable architecture with clean separation between API, business logic, and ML components.

## Table of Contents

- [Background](#background)
- [Installation](#installation)
- [Usage](#usage)
- [API](#api)
- [Architecture](#architecture)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

## Background

This microservice is designed to provide personalized travel experiences through AI-driven recommendations and intelligent traveler matching. It leverages machine learning models to understand user preferences, analyze travel patterns, and suggest compatible travel companions.

### Core Features

- **Personalized Recommendations**: AI-driven travel suggestions based on user preferences and context
- **User Profiling**: Dynamic user preference learning and behavior analysis
- **Context-Aware Suggestions**: Location-based and time-sensitive recommendations
- **Traveler Matching**: Find compatible travel partners based on preferences and travel styles
- **Real-time Processing**: Fast response times with caching and optimization
- **Scalable Architecture**: Modular design for easy maintenance and extension

## Installation

### Prerequisites

- Python 3.11+
- Redis (for caching)
- PostgreSQL or SQLite (for data storage)
- Docker (optional, for containerized deployment)

### Local Setup

1. **Clone repository**
   ```bash
   git clone https://github.com/LePeanutButter/voyager-ai-service
   cd voyager-ai-service
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize database**
   ```bash
   # For SQLite (default)
   # Database will be created automatically
   
   # For PostgreSQL
   # Set DATABASE_URL in .env
   # Run migrations: alembic upgrade head
   ```

## Usage

### Running the Service

#### Development
```bash
python -m app.main
```

#### Production
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Docker
```bash
docker build -t tourism-assistant .
docker run -p 8000:8000 tourism-assistant
```

### Accessing the Service

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Base URL**: http://localhost:8000

## API

### Authentication

Currently using mock authentication. In production, implement JWT or OAuth2.

### Endpoints

#### Recommendations

- `POST /api/v1/recommendations/personalized` - Get personalized recommendations
- `GET /api/v1/recommendations/popular/{location}` - Get popular activities
- `GET /api/v1/recommendations/trending` - Get trending activities
- `GET /api/v1/recommendations/similar/{activity_id}` - Get similar activities
- `POST /api/v1/recommendations/feedback` - Submit feedback

#### Users

- `POST /api/v1/users/profile` - Create user profile
- `GET /api/v1/users/profile/{user_id}` - Get user profile
- `PUT /api/v1/users/profile/{user_id}` - Update user profile
- `POST /api/v1/users/interaction` - Record interaction
- `GET /api/v1/users/insights/{user_id}` - Get user insights

#### Traveler Matching

- `POST /api/v1/matching/find` - Find travel partners
- `GET /api/v1/matching/compatibility/{user_id}/{target_user_id}` - Get compatibility score
- `POST /api/v1/matching/connect/{user_id}/{target_user_id}` - Initiate connection
- `GET /api/v1/matching/connections/{user_id}` - Get user connections

### Example Request

```http
POST /api/v1/recommendations/personalized
Content-Type: application/json

{
  "user_id": "user123",
  "location": {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "city": "New York",
    "country": "USA",
    "radius_km": 10.0
  },
  "preferences": ["cultural", "foodie"],
  "max_results": 10,
  "date_range": {
    "start": "2024-06-01T00:00:00Z",
    "end": "2024-06-07T00:00:00Z"
  },
  "group_size": 2,
  "budget_limit": 500
}
```

## Architecture

### Project Structure

```
app/
├── main.py                 # FastAPI application entry point
├── core/
│   └── config.py          # Configuration management
├── models/
│   ├── schemas.py         # Pydantic data models
│   └── database.py        # SQLAlchemy database models
├── routes/
│   ├── recommendations.py # Recommendation endpoints
│   ├── users.py          # User management endpoints
│   └── matching.py       # Traveler matching endpoints
├── services/
│   ├── recommendation_service.py  # Business logic for recommendations
│   ├── user_service.py            # User profile management
│   └── matching_service.py       # Traveler matching logic
├── ml/
│   └── model_loader.py    # ML model management
├── data/
│   └── processor.py       # Data preprocessing and feature engineering
└── utils/                 # Utility functions
```

### ML Pipeline

#### Model Types

1. **Recommendation Model**: Collaborative filtering and content-based recommendations
2. **User Profiling Model**: Preference learning and behavior prediction
3. **Traveler Matching Model**: Compatibility scoring and matching algorithms

#### Model Management

Models are managed through the `ModelManager` class which handles:
- Loading and caching models
- Model validation and health checks
- Runtime model updates
- Performance monitoring

#### Feature Engineering

The data processor handles:
- User preference encoding
- Location-based features
- Temporal features
- Text processing and sentiment analysis
- Geospatial calculations

### Data Models

#### User Profile

```json
{
  "user_id": "string",
  "name": "string",
  "email": "string",
  "age": "integer",
  "location": "string",
  "preferences": {
    "preferences": ["adventure", "cultural"],
    "budget_range": {"min": 50, "max": 200},
    "travel_style": "mid-range",
    "group_size": 2,
    "accessibility_needs": [],
    "dietary_restrictions": [],
    "language_preferences": []
  },
  "travel_history": [],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### Activity

```json
{
  "activity_id": "string",
  "name": "string",
  "category": "sightseeing|dining|outdoor|entertainment|shopping|educational|sports|wellness",
  "description": "string",
  "location": {
    "latitude": "float",
    "longitude": "float",
    "city": "string",
    "country": "string",
    "address": "string",
    "radius_km": "float"
  },
  "rating": "float (0-5)",
  "price_range": "$|$$|$$$|$$$$",
  "duration_hours": "float",
  "tags": ["string"],
  "requirements": ["string"],
  "best_time_to_visit": "string",
  "images": ["string"]
}
```

#### Travel Preference Categories

- `adventure`: Hiking, extreme sports, exploration
- `cultural`: Museums, historical sites, local experiences
- `relaxation`: Spas, beaches, leisure activities
- `nature`: Parks, wildlife, natural attractions
- `urban`: City tours, shopping, nightlife
- `foodie`: Restaurants, food tours, culinary experiences
- `historical`: Heritage sites, monuments, museums
- `shopping`: Markets, malls, local crafts
- `nightlife`: Bars, clubs, evening entertainment
- `family_friendly`: Activities suitable for children

## Development

### Environment Variables

```bash
# Service Configuration
SERVICE_NAME=tourism-assistant
DEBUG=false

# Database
DATABASE_URL=sqlite:///./tourism_assistant.db

# Redis (for caching)
REDIS_URL=redis://localhost:6379

# ML Models
MODEL_PATH=./app/ml/models
RECOMMENDATION_MODEL=recommendation_model.pkl
USER_PROFILING_MODEL=user_profiling_model.pkl
MATCHING_MODEL=traveler_matching_model.pkl

# External APIs
WEATHER_API_KEY=your_weather_api_key
MAPS_API_KEY=your_maps_api_key

# Logging
LOG_LEVEL=INFO
```

### Code Style

```bash
black app/
isort app/
flake8 app/
mypy app/
```

### Adding New Features

1. **Add Models**: Define data models in `app/models/schemas.py`
2. **Implement Services**: Add business logic in `app/services/`
3. **Create Routes**: Add API endpoints in `app/routes/`
4. **Write Tests**: Add unit and integration tests
5. **Update Documentation**: Update API documentation

### ML Model Updates

1. **Train Models**: Use training pipeline in `app/ml/training/`
2. **Validate Models**: Test with validation datasets
3. **Update Model Files**: Replace model files in `app/ml/models/`
4. **Reload Models**: Use reload endpoint or restart service

## Testing

### Unit Tests

```bash
pytest tests/unit/
```

### Integration Tests

```bash
pytest tests/integration/
```

### API Tests

```bash
pytest tests/api/
```

### Coverage

```bash
pytest --cov=app tests/
```

## Deployment

### Docker Deployment

The project includes a production-ready Dockerfile with multi-stage builds:

```bash
# Build image
docker build -t tourism-assistant .

# Run container
docker run -p 8000:8000 tourism-assistant
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tourism-assistant
spec:
  replicas: 3
  selector:
    matchLabels:
      app: tourism-assistant
  template:
    metadata:
      labels:
        app: tourism-assistant
    spec:
      containers:
      - name: tourism-assistant
        image: tourism-assistant:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
```

### Performance Considerations

#### Caching Strategy
- Redis for recommendation caching
- In-memory caching for frequently accessed data
- TTL-based cache invalidation

#### Scalability
- Horizontal scaling with multiple workers
- Database connection pooling
- Asynchronous processing for ML predictions

#### Monitoring
- Prometheus metrics for performance monitoring
- Structured logging for debugging
- Health check endpoints for monitoring

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.

### License Summary

- **Commercial Use**: Yes
- **Modification**: Yes
- **Distribution**: Yes
- **Private Use**: Yes
- **Liability**: No
- **Warranty**: No

### Copyright

© 2026 Voyager Team. All rights reserved.