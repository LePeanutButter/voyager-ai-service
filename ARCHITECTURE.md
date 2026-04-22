# ARCHITECTURE.md
SYSTEM TEMPLATE FOR RAPID CODEBASE COMPREHENSION - HAVE YOUR AGENT TO FILL IN FOR YOUR REPO

# Architecture Overview
This document serves as a critical, living template designed to equip agents with a rapid and comprehensive understanding of the codebase's architecture, enabling efficient navigation and effective contribution from day one. Update this document as the codebase evolves.

---

## 1. Project Structure

This project follows a **multi-repository architecture**. The structure below represents a **logical unified view** of the system:

```
[Project Root]/
├── mobile-app/               # Android application (Kotlin)
│   ├── app/
│   │   ├── src/main/
│   │   │   ├── data/        # API, repositories, local storage
│   │   │   ├── domain/      # Use cases and business rules
│   │   │   ├── presentation/# UI, ViewModels
│   │   │   └── di/          # Dependency injection (Hilt)
│   ├── build.gradle
│   └── AndroidManifest.xml
│
├── backend-api/             # Main backend (Spring Boot)
│   ├── src/main/java/
│   │   ├── controller/      # REST controllers
│   │   ├── service/         # Business logic
│   │   ├── repository/      # Data access layer
│   │   ├── model/           # Entities
│   │   ├── dto/             # Data transfer objects
│   │   └── config/          # Security and configs
│   ├── src/main/resources/
│   │   └── application.yml
│   └── Dockerfile
│
├── ai-service/              # AI microservice (Python)
│   ├── app/
│   │   ├── routes/          # API endpoints
│   │   ├── services/        # Recommendation logic
│   │   ├── models/          # ML models
│   │   ├── schemas/         # Request/response schemas
│   │   └── utils/           # Helpers
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── web-portal/              # React frontend
│   ├── src/
│   │   ├── components/      # UI components
│   │   ├── pages/           # Views
│   │   ├── services/        # API calls
│   │   ├── hooks/           # Custom hooks
│   │   └── store/           # State management
│   ├── public/
│   └── package.json
│
├── docs/                    # Documentation
├── scripts/                 # Automation scripts
├── .github/                 # CI/CD configs
├── README.md
└── ARCHITECTURE.md
```

---

## 2. High-Level System Diagram

```mermaid
flowchart LR

User <--> MobileApp
User <--> WebApp

MobileApp <--> BackendAPI
WebApp <--> BackendAPI

BackendAPI <--> Database
BackendAPI <--> AIMicroservice
BackendAPI <--> ExternalAPIs
````

---

## 3. Core Components

### 3.1. Frontend

Name: Mobile App & Web Portal

Description:
User-facing interfaces that allow travelers to interact with the platform, receive AI-powered recommendations, plan trips, and connect with other users.

Technologies:

* Kotlin (Android)
* React (Web)

Deployment:

* Mobile: Google Play Store
* Web: AWS S3 + CloudFront

---

### 3.2. Backend Services

#### 3.2.1. Backend API

Name: Core Backend API

Description:
Central system responsible for business logic, user management, reservations, and orchestration between services.

Technologies:

* Java (Spring Boot)

Deployment:

* AWS ECS / Elastic Beanstalk

---

#### 3.2.2. AI Microservice

Name: AI Recommendation Service

Description:
Provides personalized travel recommendations, user profiling, and intelligent matching between travelers.

Technologies:

* Python (FastAPI)

Deployment:

* AWS ECS / Lambda

---

## 4. Data Stores

### 4.1. Primary Database

Name: Main Application Database

Type: PostgreSQL (AWS RDS)

Purpose:
Stores core application data including users, bookings, preferences, and interactions.

Key Schemas/Collections:

* users
* bookings
* preferences
* reviews

---

### 4.2. Object Storage

Name: Media & Assets Storage

Type: AWS S3

Purpose:
Stores images, documents, and static assets.

---

## 5. External Integrations / APIs

Service Name 1: Payment Gateway (e.g., Stripe)
Purpose: Payment processing
Integration Method: REST API

Service Name 2: Tourism Providers APIs
Purpose: Retrieve services, availability, and pricing
Integration Method: REST API

---

## 6. Deployment & Infrastructure

Cloud Provider: AWS

Key Services Used:

* ECS / Elastic Beanstalk
* S3 + CloudFront
* RDS
* Lambda (optional)

CI/CD Pipeline:

* Azure DevOps Pipelines

Monitoring & Logging:

* AWS CloudWatch
* AWS X-Ray

---

## 7. Security Considerations

Authentication:

* JWT

Authorization:

* Role-Based Access Control (RBAC)

Data Encryption:

* HTTPS (TLS) in transit
* Encrypted storage at rest

Key Security Tools/Practices:

* Secure API endpoints
* Environment-based configuration
* Secrets management

---

## 8. Development & Testing Environment

Local Setup Instructions:
See README.md for setup per repository

Testing Frameworks:

* JUnit (Backend)
* Pytest (AI Service)
* Jest (Frontend)

Code Quality Tools:

* ESLint
* SonarQube
* Prettier

---

## 9. Future Considerations / Roadmap

* Implement event-driven architecture (Kafka)
* Enhance AI models with deep learning
* Real-time recommendations
* Expand social features between travelers

---

## 10. Project Identification

Project Name: SmarTrip

Primary Contact/Team: Voyager

Date of Last Update: 2026-04-21

---

## 11. Glossary / Acronyms

AI: Artificial Intelligence
API: Application Programming Interface
JWT: JSON Web Token
RBAC: Role-Based Access Control
CI/CD: Continuous Integration / Continuous Deployment
ML: Machine Learning
