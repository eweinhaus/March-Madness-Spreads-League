import React, { useState } from 'react';
import { Form, Button, Alert, Container, Row, Col } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { API_URL } from "../config";

const ForgotPassword = () => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
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
    setSuccess('');
    setLoading(true);
    console.log('Starting password reset process...');

    try {
      console.log('Sending password reset request...');
      const response = await fetch(`${API_URL}/forgot-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: formData.username,
          email: formData.email,
        }),
      });

      console.log('Password reset response received:', response.status);
      const data = await response.json();
      console.log('Password reset data:', data);

      if (!response.ok) {
        throw new Error(data.detail || 'Password reset failed');
      }

      setSuccess(data.message || 'Password reset successful! Check your email for the new password.');
      setFormData({ username: '', email: '' });
      
    } catch (err) {
      console.error('Error during password reset:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container className="mt-3 mt-md-5 px-3 px-md-4">
      <Row className="justify-content-center">
        <Col xs={12} sm={10} md={8} lg={6} xl={5}>
          <div className="bg-white p-3 p-md-4 rounded shadow-sm">
            <h2 className="text-center mb-3 mb-md-4">Forgot Password</h2>
            <p className="text-center text-muted mb-4">
              Enter your username and email address to reset your password.
            </p>
            
            {error && <Alert variant="danger">{error}</Alert>}
            {success && <Alert variant="success">{success}</Alert>}
            
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
                  disabled={loading}
                />
              </Form.Group>

              <Form.Group className="mb-4">
                <Form.Label>Email</Form.Label>
                <Form.Control
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  required
                  className="py-2"
                  disabled={loading}
                />
              </Form.Group>

              <div className="d-grid gap-2">
                <Button 
                  variant="primary" 
                  type="submit" 
                  className="py-2"
                  disabled={loading}
                >
                  {loading ? 'Processing...' : 'Reset Password'}
                </Button>
                <Button 
                  variant="outline-secondary" 
                  onClick={() => navigate('/login')}
                  className="py-2 mt-1"
                  disabled={loading}
                >
                  Back to Login
                </Button>
              </div>
            </Form>
          </div>
        </Col>
      </Row>
    </Container>
  );
};

export default ForgotPassword; 