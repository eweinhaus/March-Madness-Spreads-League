# March Madness Spreads

This web application is currently being utilized by 40+ active users to track and score a college basketball spread picking pool for the 2025 March Madness season.

You can view the live site here: 
https://march-madness-spreads-league.onrender.com/leaderboard


## Features

- User authentication and registration
- Admin interface for managing games and spreads
- User interface for submitting picks
- Live leaderboard tracking
- Real-time game updates

## Tech Stack

- Frontend: React with Vite
- Backend: FastAPI (Python)
- Database: PostgreSQL
- Authentication: JWT

## Prerequisites

- Python 3.9+
- Node.js 16+
- PostgreSQL

## Future Plans:
- Implement ESPN Live CBB Game API to handle all scores and updates automatically
- Handle payment processing for users through the webapp directly
- Create functionality for multiple leagues, allowing additional groups to participate

## Setup

### Backend Setup

1. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the `march_madness_backend` directory with:
```
DATABASE_URL=postgresql://user:password@localhost:5432/march_madness
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

4. Run the backend server:
```bash
cd march_madness_backend
uvicorn main:app --reload
```

### Frontend Setup

1. Install dependencies:
```bash
cd march-madness-frontend
npm install
```

2. Run the development server:
```bash
npm run dev
```

## Usage

1. Register a new account or log in
2. View available games and spreads
3. Submit your picks for games
4. Track your performance on the leaderboard

## API Documentation

Once the backend server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
