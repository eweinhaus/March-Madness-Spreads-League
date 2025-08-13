import React, { useState } from 'react';
import { Form, Button, Alert, Container, Row, Col } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { API_URL } from "../config";

const Register = () => {
  const [formData, setFormData] = useState({
    username: '',
    full_name: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    console.log('Starting registration process...');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    try {
      console.log('Sending registration request...');
      // Register the user
      const registerResponse = await fetch(`${API_URL}/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: formData.username,
          full_name: formData.full_name,
          email: formData.email,
          password: formData.password,
        }),
      });

      console.log('Registration response received:', registerResponse.status);
      const registerData = await registerResponse.json();
      console.log('Registration data:', registerData);

      if (!registerResponse.ok) {
        throw new Error(registerData.detail || 'Registration failed');
      }

      console.log('Registration successful, attempting auto-login...');
      // Automatically log in the user
      const loginResponse = await fetch(`${API_URL}/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          username: formData.username,
          password: formData.password,
        }),
      });

      console.log('Login response received:', loginResponse.status);
      const loginData = await loginResponse.json();
      console.log('Login data:', loginData);

      if (!loginResponse.ok) {
        throw new Error(loginData.detail || 'Auto-login failed');
      }

      // Store the token
      localStorage.setItem('token', loginData.access_token);
      console.log('Token stored, redirecting...');
      
      // Redirect to home page
      navigate('/');
      
      // Force a page reload to update the navigation bar
      window.location.reload();
    } catch (err) {
      console.error('Error during registration/login:', err);
      setError(err.message);
    }
  };

  return (
    <Container className="mt-3 mt-md-5 px-3 px-md-4">
      <Row className="justify-content-center">
        <Col xs={12} sm={10} md={8} lg={6} xl={5}>
          <div className="bg-white p-3 p-md-4 rounded shadow-sm">
            <h2 className="text-center mb-3 mb-md-4">Register</h2>
            {error && <Alert variant="danger">{error}</Alert>}
            <Form onSubmit={handleSubmit}>
              <Form.Group className="mb-3">
                <Form.Label>Username</Form.Label>
                <Form.Control
                  type="text"
                  name="username"
                  value={formData.username}
                  onChange={handleChange}
                  required
                  className="py-2"
                />
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label>Full Name</Form.Label>
                <Form.Control
                  type="text"
                  name="full_name"
                  value={formData.full_name}
                  onChange={handleChange}
                  required
                  className="py-2"
                />
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label>Email</Form.Label>
                <Form.Control
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  required
                  className="py-2"
                />
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label>Password</Form.Label>
                <Form.Control
                  type="password"
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  required
                  className="py-2"
                />
              </Form.Group>

              <Form.Group className="mb-4">
                <Form.Label>Confirm Password</Form.Label>
                <Form.Control
                  type="password"
                  name="confirmPassword"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  required
                  className="py-2"
                />
              </Form.Group>

              <div className="d-grid gap-2">
                <Button variant="primary" type="submit" className="py-2">
                  Register
                </Button>
                <Button 
                  variant="outline-secondary" 
                  onClick={() => navigate('/login')}
                  className="py-2 mt-1"
                >
                  Already have an account? Login
                </Button>
              </div>
            </Form>
          </div>
        </Col>
      </Row>
    </Container>
  );
};

export default Register; 