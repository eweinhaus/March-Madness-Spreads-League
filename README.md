# March Madness Spreads

A web application for managing and tracking March Madness basketball game spreads and user picks.

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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 