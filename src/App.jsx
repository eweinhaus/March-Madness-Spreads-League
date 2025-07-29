import AdminUserPicks from './pages/AdminUserPicks';

function App() {
  return (
    <Router>
      <Navbar bg="light" expand="lg">
        <Container>
          <Navbar.Brand as={Link} to="/">Spreads</Navbar.Brand>
          <Nav className="me-auto">
            <Nav.Link as={Link} to="/">Home</Nav.Link>
            <Nav.Link as={Link} to="/picks">Picks</Nav.Link>
            <Nav.Link as={Link} to="/leaderboard">Leaderboard</Nav.Link>
            <Nav.Link as={Link} to="/live">Live</Nav.Link>
            <ProtectedRoute adminOnly={true}>
              <Nav.Link as={Link} to="/admin/user-picks">User Picks Status</Nav.Link>
            </ProtectedRoute>
            <Nav.Link as={Link} to="/login">Login</Nav.Link>
            <Nav.Link as={Link} to="/register">Register</Nav.Link>
          </Nav>
        </Container>
      </Navbar>
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/picks" element={<Picks />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/live" element={<Live />} />
          <Route path="/admin/user-picks" element={
            <ProtectedRoute adminOnly={true}>
              <AdminUserPicks />
            </ProtectedRoute>
          } />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
        </Routes>
      </main>
    </Router>
  );
}

export default App; 