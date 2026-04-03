import { BrowserRouter as Router, Routes, Route, Link, Navigate, useNavigate } from 'react-router-dom';
import { Container, Nav, Navbar, Button } from 'react-bootstrap';
import { useState, useEffect } from 'react';
import { FaLock } from 'react-icons/fa';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';
import { onAuthStateChanged } from 'firebase/auth';
import { auth, signOut } from './firebase';
import api from './api';

import Home from './pages/Home';
import Picks from './pages/Picks';
import Leaderboard from './pages/Leaderboard';
import Stats from './pages/Stats';
import AdminGames from './pages/AdminGames';
import AdminUserPicks from './pages/AdminUserPicks';
import AdminTiebreakers from './pages/AdminTiebreakers';
import Login from './pages/Login';
import Live from './pages/Live';

function ProtectedRoute({ children, adminOnly = false }) {
  const [firebaseUser, setFirebaseUser] = useState(undefined);
  const [appUser, setAppUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [meFetchFailed, setMeFetchFailed] = useState(false);

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async (fbUser) => {
      setMeFetchFailed(false);
      setFirebaseUser(fbUser);
      if (!fbUser) {
        setAppUser(null);
        setLoading(false);
        return;
      }
      try {
        const res = await api.get('/users/me');
        setAppUser(res.data);
      } catch {
        setAppUser(null);
        setMeFetchFailed(true);
      }
      setLoading(false);
    });
    return unsub;
  }, []);

  if (loading) return <div>Loading...</div>;
  if (!firebaseUser || meFetchFailed) return <Navigate to="/login" replace />;
  if (adminOnly && appUser && !appUser.admin) return <Navigate to="/" />;
  return children;
}

function AppContent() {
  const [firebaseUser, setFirebaseUser] = useState(undefined);
  const [isAdmin, setIsAdmin] = useState(false);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async (fbUser) => {
      setFirebaseUser(fbUser);
      if (fbUser) {
        try {
          const res = await api.get('/users/me');
          setUser(res.data);
          setIsAdmin(res.data.admin);
        } catch {
          setUser(null);
          setIsAdmin(false);
        }
      } else {
        setUser(null);
        setIsAdmin(false);
      }
    });
    return unsub;
  }, []);

  const handleLogout = async () => {
    await signOut(auth);
    setUser(null);
    setIsAdmin(false);
    navigate('/login');
  };

  const isAuthenticated = !!firebaseUser;

  return (
    <div className="App">
      <Navbar bg="dark" variant="dark" expand="lg" className="navbar" collapseOnSelect>
        <Container>
          <Navbar.Brand as={Link} to="/">Spreads</Navbar.Brand>
          <Navbar.Toggle aria-controls="basic-navbar-nav" />
          <Navbar.Collapse id="basic-navbar-nav">
            <Nav className="me-auto">
              <Nav.Link as={Link} to="/" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler')?.click()}>Home</Nav.Link>
              <Nav.Link as={Link} to="/picks" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler')?.click()}>Picks</Nav.Link>
              <Nav.Link as={Link} to="/leaderboard" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler')?.click()}>Leaderboard</Nav.Link>
              {/* Stats temporarily hidden - reimplement later */}
              <Nav.Link as={Link} to="/live" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler')?.click()}>Live</Nav.Link>
              {isAuthenticated && isAdmin && (
                <Nav.Link as={Link} to="/admin/games" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler')?.click()}><FaLock className="me-1" />Games</Nav.Link>
              )}
              {isAuthenticated && isAdmin && (
                <Nav.Link as={Link} to="/admin/tiebreakers" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler')?.click()}><FaLock className="me-1" />Questions</Nav.Link>
              )}
              {isAuthenticated && isAdmin && (
                <Nav.Link as={Link} to="/admin/user-picks" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler')?.click()}><FaLock className="me-1" />User Picks</Nav.Link>
              )}
            </Nav>
            <Nav>
              {isAuthenticated ? (
                <div className="d-flex align-items-center">
                  {user && <span className="text-light me-2 d-none d-sm-inline">{user.display_name || user.email}</span>}
                  <Button variant="outline-light" onClick={handleLogout}>Logout</Button>
                </div>
              ) : (
                <Nav.Link as={Link} to="/login" onClick={() => window.innerWidth < 992 && document.querySelector('.navbar-toggler')?.click()}>Sign In</Nav.Link>
              )}
            </Nav>
          </Navbar.Collapse>
        </Container>
      </Navbar>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login setUser={setUser} />} />
          <Route path="/picks" element={
            <ProtectedRoute>
              <Picks />
            </ProtectedRoute>
          } />
          <Route path="/live" element={<Live />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/stats" element={<Stats />} />
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
