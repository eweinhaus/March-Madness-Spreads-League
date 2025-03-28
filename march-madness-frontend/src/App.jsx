import { BrowserRouter as Router, Routes, Route, Link, Navigate, useNavigate } from 'react-router-dom';
import { Container, Nav, Navbar, Button } from 'react-bootstrap';
import { useState, useEffect } from 'react';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';
import axios from 'axios';
import { API_URL } from "./config";

import Home from './pages/Home';
import Picks from './pages/Picks';
import Leaderboard from './pages/Leaderboard';
import AdminGames from './pages/AdminGames';
import AdminUserPicks from './pages/AdminUserPicks';
import AdminTiebreakers from './pages/AdminTiebreakers';
import Login from './pages/Login';
import Register from './pages/Register';
import Live from './pages/Live';

function ProtectedRoute({ children, adminOnly = false }) {
  const token = localStorage.getItem('token');
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const checkUser = async () => {
      if (!token) {
        console.log('ProtectedRoute - No token found, redirecting to login');
        setLoading(false);
        navigate('/login');
        return;
      }

      // Log token information for debugging (without exposing the full token)
      console.log('ProtectedRoute - Token exists:', !!token);
      console.log('ProtectedRoute - Token length:', token.length);
      console.log('ProtectedRoute - Token starts with:', token.substring(0, 10) + '...');
      
      try {
        console.log('ProtectedRoute - Validating token with /users/me endpoint');
        const response = await fetch(`${API_URL}/users/me`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        // Log response status
        console.log('ProtectedRoute - /users/me response status:', response.status);
        
        if (!response.ok) {
          // If response is not OK, try to get more details
          try {
            const errorData = await response.json();
            console.error('ProtectedRoute - Error response data:', errorData);
            
            // Log the error message, but always redirect on 401
            if (errorData && errorData.detail) {
              console.log('ProtectedRoute - Error detail:', errorData.detail);
            }
          } catch (jsonError) {
            console.error('ProtectedRoute - Could not parse error response:', jsonError);
          }
          
          // Any 401 should redirect to login
          console.log('ProtectedRoute - Authentication failed, redirecting to login');
          localStorage.removeItem('token');
          navigate('/login');
          return;
        }
        
        const data = await response.json();
        console.log('ProtectedRoute - User authenticated successfully');
        setIsAdmin(data.is_admin);
      } catch (error) {
        console.error('ProtectedRoute - Error checking user:', error);
        localStorage.removeItem('token');
        navigate('/login');
      }
      setLoading(false);
    };

    checkUser();
  }, [token, navigate]);

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!token) {
    return <Navigate to="/login" />;
  }

  if (adminOnly && !isAdmin) {
    return <Navigate to="/" />;
  }

  return children;
}

function AppContent() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('token'));
  const [isAdmin, setIsAdmin] = useState(false);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsAuthenticated(false);
    setIsAdmin(false);
    setUser(null);
  };

  useEffect(() => {
    const token = localStorage.getItem('token');
    setIsAuthenticated(!!token);

    if (token) {
      console.log('AppContent - Token found, verifying with /users/me');
      // Log token information for debugging (without exposing the full token)
      console.log('AppContent - Token exists:', !!token);
      console.log('AppContent - Token length:', token.length);
      console.log('AppContent - Token starts with:', token.substring(0, 10) + '...');
      
      fetch(`${API_URL}/users/me`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
        .then(res => {
          console.log('AppContent - /users/me response status:', res.status);
          
          if (!res.ok) {
            // If response is not OK, throw error to be caught in catch block
            return res.json().then(errorData => {
              console.error('AppContent - Error response data:', errorData);
              
              // Log error message for debugging
              if (errorData && errorData.detail) {
                console.log('AppContent - Error detail:', errorData.detail);
              }
              
              // Always throw on 401, regardless of specific error message
              throw new Error('Authentication failed');
            });
          }
          
          return res.json();
        })
        .then(data => {
          console.log('AppContent - User authenticated successfully');
          setIsAdmin(data.is_admin);
          setUser(data);
        })
        .catch(err => {
          console.error('AppContent - Error checking user:', err);
          localStorage.removeItem('token');
          setIsAuthenticated(false);
          setIsAdmin(false);
          setUser(null);
        });
    }
  }, []);

  return (
    <div className="App">
      <Navbar bg="dark" variant="dark" expand="lg" className="navbar" collapseOnSelect>
        <Container>
          <Navbar.Brand as={Link} to="/">March Madness Spreads</Navbar.Brand>
          <Navbar.Toggle aria-controls="basic-navbar-nav" />
          <Navbar.Collapse id="basic-navbar-nav">
            <Nav className="me-auto">
              <Nav.Link as={Link} to="/" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler').click()}>Home</Nav.Link>
              <Nav.Link as={Link} to="/picks" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler').click()}>Picks</Nav.Link>
              <Nav.Link as={Link} to="/leaderboard" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler').click()}>Leaderboard</Nav.Link>
              <Nav.Link as={Link} to="/live" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler').click()}>Live</Nav.Link>
              {isAuthenticated && isAdmin && (
                <Nav.Link as={Link} to="/admin/games" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler').click()}>$Games</Nav.Link>
              )}
              {isAuthenticated && isAdmin && (
                <Nav.Link as={Link} to="/admin/tiebreakers" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler').click()}>$Questions</Nav.Link>
              )}
              {isAuthenticated && isAdmin && (
                <Nav.Link as={Link} to="/admin/user-picks" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler').click()}>$User Picks</Nav.Link>
              )}
            </Nav>
            <Nav>
              {isAuthenticated ? (
                <div className="d-flex align-items-center">
                  {user && <span className="text-light me-2 d-none d-sm-inline">{user.username}</span>}
                  <Button variant="outline-light" onClick={handleLogout}>Logout</Button>
                </div>
              ) : (
                <div className="d-flex flex-column flex-sm-row">
                  <Nav.Link as={Link} to="/login" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler').click()}>Login</Nav.Link>
                  <Nav.Link as={Link} to="/register" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler').click()}>Register</Nav.Link>
                </div>
              )}
            </Nav>
          </Navbar.Collapse>
        </Container>
      </Navbar>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login setUser={setUser} />} />
          <Route path="/register" element={<Register setUser={setUser} />} />
          <Route path="/picks" element={
            <ProtectedRoute>
              <Picks />
            </ProtectedRoute>
          } />
          <Route path="/live" element={<Live />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/admin/games" element={
            <ProtectedRoute adminOnly={true}>
              <AdminGames />
            </ProtectedRoute>
          } />
          <Route path="/admin/user-picks" element={
            <ProtectedRoute adminOnly={true}>
              <AdminUserPicks />
            </ProtectedRoute>
          } />
          <Route path="/admin/tiebreakers" element={
            <ProtectedRoute adminOnly={true}>
              <AdminTiebreakers />
            </ProtectedRoute>
          } />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;
