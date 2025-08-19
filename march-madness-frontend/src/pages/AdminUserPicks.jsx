import React, { useState, useEffect } from 'react';
import { Container, Table, Alert, Card, Row, Col } from 'react-bootstrap';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { API_URL } from '../config';
import UserPicksModal from '../components/UserPicksModal';

const AdminUserPicks = () => {
  const [userPicksStatus, setUserPicksStatus] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedUserPicks, setSelectedUserPicks] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchUserPicksStatus = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          navigate('/login');
          return;
        }

        const response = await axios.get(`${API_URL}/admin/user_picks_status`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setUserPicksStatus(response.data);
      } catch (err) {
        if (err.response?.status === 401) {
          navigate('/login');
        } else {
          setError('Failed to fetch user picks status');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchUserPicksStatus();
  }, [navigate]);

  const handleUserClick = async (username) => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API_URL}/admin/user_all_picks/${username}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSelectedUserPicks(response.data);
      setShowModal(true);
    } catch (err) {
      if (err.response?.status === 401) {
        navigate('/login');
      } else if (err.response?.status === 404) {
        // User not found or doesn't have make_picks permission
        setError('User not found or does not have permission to make picks');
      } else {
        setError('Failed to fetch user picks');
      }
    }
  };

  if (loading) {
    return (
      <Container className="d-flex justify-content-center align-items-center" style={{ minHeight: '80vh' }}>
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </Container>
    );
  }

  if (error) {
    return (
      <Container className="mt-4">
        <Alert variant="danger">
          <Alert.Heading>Error!</Alert.Heading>
          <p>{error}</p>
        </Alert>
      </Container>
    );
  }

  const totalUsers = userPicksStatus.length;
  const completedUsers = userPicksStatus.filter(user => user.is_complete).length;
  const completionRate = ((completedUsers / totalUsers) * 100).toFixed(1);

  return (
    <Container className="mt-4">
      <Card className="mb-4">
        <Card.Body>
          <Card.Title className="h3 mb-4">Upcoming Picks Status</Card.Title>
          <Row>
            <Col md={4}>
              <Card className="mb-3">
                <Card.Body className="bg-light">
                  <Card.Title className="h5 text-primary">Total Users</Card.Title>
                  <Card.Text className="h2 text-primary">{totalUsers}</Card.Text>
                </Card.Body>
              </Card>
            </Col>
            <Col md={4}>
              <Card className="mb-3">
                <Card.Body className="bg-light">
                  <Card.Title className="h5 text-success">Users With All Picks Submitted</Card.Title>
                  <Card.Text className="h2 text-success">{completedUsers}</Card.Text>
                </Card.Body>
              </Card>
            </Col>
            <Col md={4}>
              <Card className="mb-3">
                <Card.Body className="bg-light">
                  <Card.Title className="h5 text-info">Completion Rate</Card.Title>
                  <Card.Text className="h2 text-info">{completionRate}%</Card.Text>
                </Card.Body>
              </Card>
            </Col>
          </Row>
        </Card.Body>
      </Card>

      <Card>
        <Card.Body>
          <Table striped bordered hover responsive size="sm">
            <thead>
              <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
                <th className="py-2">Name</th>
                <th className="py-2">Progress</th>
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody className="small">
              {userPicksStatus
                .sort((a, b) => {
                  // First sort by completion status (incomplete first)
                  if (a.is_complete !== b.is_complete) {
                    return a.is_complete ? 1 : -1;
                  }
                  // Then sort by name alphabetically
                  return a.full_name.localeCompare(b.full_name);
                })
                .map((user) => (
                <tr 
                  key={user.username}
                  onClick={() => handleUserClick(user.username)}
                  style={{ cursor: 'pointer', fontSize: '0.85rem', lineHeight: '1.2' }}
                  className="user-row"
                >
                  <td className="py-2">{user.full_name}</td>
                  <td className="py-2">
                    <div className="d-flex align-items-center">
                      <div className="progress flex-grow-1 me-2" style={{ height: '18px' }}>
                        <div
                          className="progress-bar"
                          role="progressbar"
                          style={{
                            width: `${(user.picks_made / user.total_games) * 100}%`,
                            backgroundColor: user.is_complete ? '#198754' : '#ffc107',
                            fontSize: '0.75rem'
                          }}
                          aria-valuenow={user.picks_made}
                          aria-valuemin="0"
                          aria-valuemax={user.total_games}
                        >
                          {user.picks_made}/{user.total_games}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="py-2">
                    <span 
                      className={`badge ${user.is_complete ? 'bg-success' : 'bg-warning'}`}
                      style={{ fontSize: '0.75rem', padding: '0.25em 0.5em' }}
                    >
                      {user.is_complete ? 'All Picks Submitted' : 'Missing Picks'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card.Body>
      </Card>

      <UserPicksModal
        show={showModal}
        onHide={() => setShowModal(false)}
        userPicks={selectedUserPicks}
        isAdmin={true}
      />

      <style jsx>{`
        .user-row:hover {
          background-color: rgba(0, 0, 0, 0.075) !important;
        }
      `}</style>
    </Container>
  );
};

export default AdminUserPicks; 