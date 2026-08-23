import { Container, Alert, Button } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';

export default function NotFound() {
  const navigate = useNavigate();

  return (
    <Container className="my-5">
      <Alert variant="warning" className="text-center">
        <h2 className="mb-3">Page Not Found</h2>
        <p className="mb-4">The page you're looking for doesn't exist.</p>
        <Button variant="primary" onClick={() => navigate('/')}>
          Go Home
        </Button>
      </Alert>
    </Container>
  );
}
