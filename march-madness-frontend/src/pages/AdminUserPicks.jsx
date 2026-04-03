import React, { useState, useEffect } from 'react';
import { Container, Table, Alert, Card, Button } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import UserPicksModal from '../components/UserPicksModal';

const AdminUserPicks = () => {
  const [userPicksStatus, setUserPicksStatus] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedUserPicks, setSelectedUserPicks] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [copyEmailsFeedback, setCopyEmailsFeedback] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchUserPicksStatus = async () => {
      try {
        const response = await api.get('/admin/user_picks_status');
        setUserPicksStatus(response.data);
      } catch (err) {
        if (err.response?.status === 401) {
          navigate('/login');
        } else {
          const detail =
            err.response?.data?.detail ||
            err.response?.data?.message ||
            err.message;
          setError(
            detail
              ? `Failed to fetch user picks status: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`
              : 'Failed to fetch user picks status'
          );
        }
      } finally {
        setLoading(false);
      }
    };

    fetchUserPicksStatus();
  }, [navigate]);

  const handleUserClick = async (uid) => {
    try {
      const response = await api.get(`/admin/user_all_picks/${uid}`);
      setSelectedUserPicks(response.data);
      setShowModal(true);
    } catch (err) {
      if (err.response?.status === 401) {
        navigate('/login');
      } else if (err.response?.status === 404) {
        setError('User not found or does not have permission to make picks');
      } else {
        setError('Failed to fetch user picks');
      }
    }
  };

  const copyAllUserEmails = async () => {
    const emails = [
      ...new Set(
        userPicksStatus
          .map((u) => (u.email || '').trim().toLowerCase())
          .filter(Boolean)
      ),
    ].sort();
    if (emails.length === 0) {
      setCopyEmailsFeedback('No emails on file for these users.');
      setTimeout(() => setCopyEmailsFeedback(null), 4000);
      return;
    }
    const text = emails.join(', ');
    try {
      await navigator.clipboard.writeText(text);
      setCopyEmailsFeedback(`Copied ${emails.length} email${emails.length === 1 ? '' : 's'} to clipboard. Paste into Gmail To or Bcc.`);
    } catch {
      setCopyEmailsFeedback('Could not copy — try a secure (HTTPS) page or copy manually.');
    }
    setTimeout(() => setCopyEmailsFeedback(null), 5000);
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

  const totalGamesRequired = userPicksStatus.length > 0 ? userPicksStatus[0].total_games : 0;

  const usersWithCurrentDayLock = userPicksStatus.filter(user => user.has_current_day_lock).length;
  const locksProgressPercentage = totalUsers > 0 ? ((usersWithCurrentDayLock / totalUsers) * 100).toFixed(1) : 0;

  return (
    <Container className="mt-4">
      <Card className="mb-4">
        <Card.Body>
          <Card.Title className="h3 mb-4">Pick Submission Progress</Card.Title>
          <div className="mb-4">
            {/* Users Completion Progress Bar */}
            <div className="mb-3">
              <div className="d-flex justify-content-between align-items-center mb-2">
                <span className="h6 mb-0 fw-bold">Users Completed</span>
                <span className="h6 mb-0 text-info">{completionRate}%</span>
              </div>
              <div className="progress mb-2" style={{ height: '25px' }}>
                <div
                  className="progress-bar bg-info"
                  role="progressbar"
                  style={{
                    width: `${completionRate}%`,
                    fontSize: '0.8rem',
                    fontWeight: 'bold'
                  }}
                  aria-valuenow={completionRate}
                  aria-valuemin="0"
                  aria-valuemax="100"
                >
                  {completedUsers} / {totalUsers} users
                </div>
              </div>
              <div className="text-muted small">
                Users who have submitted all required picks
              </div>
            </div>

            {/* Locks Progress Bar */}
            <div className="mb-3">
              <div className="d-flex justify-content-between align-items-center mb-2">
                <span className="h6 mb-0 fw-bold">Locks Completed</span>
                <span className="h6 mb-0 text-warning">{locksProgressPercentage}%</span>
              </div>
              <div className="progress mb-2" style={{ height: '25px' }}>
                <div
                  className="progress-bar bg-warning"
                  role="progressbar"
                  style={{
                    width: `${locksProgressPercentage}%`,
                    fontSize: '0.8rem',
                    fontWeight: 'bold'
                  }}
                  aria-valuenow={locksProgressPercentage}
                  aria-valuemin="0"
                  aria-valuemax="100"
                >
                  {usersWithCurrentDayLock} / {totalUsers} users
                </div>
              </div>
              <div className="text-muted small">
                Users who have a lock of the day for the current 3am ET–3am ET window
              </div>
            </div>
          </div>
        </Card.Body>
      </Card>

      <Card>
        <Card.Body>
          <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
            <Button variant="outline-secondary" size="sm" onClick={copyAllUserEmails}>
              Copy all user emails
            </Button>
            <span className="text-muted small">
              Comma-separated — paste into Gmail <strong>To</strong> or <strong>Bcc</strong> for a blast.
            </span>
          </div>
          {copyEmailsFeedback && (
            <Alert variant="info" className="py-2 small mb-3" dismissible onClose={() => setCopyEmailsFeedback(null)}>
              {copyEmailsFeedback}
            </Alert>
          )}
          <Table striped bordered hover responsive size="sm">
            <thead>
              <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
                <th className="py-2">Name</th>
                <th className="py-2">Progress</th>
                <th className="py-2">Pick Status</th>
                <th className="py-2">Lock Status</th>
              </tr>
            </thead>
            <tbody className="small">
              {userPicksStatus
                .sort((a, b) => {
                  if (a.is_complete !== b.is_complete) {
                    return a.is_complete ? 1 : -1;
                  }
                  if (a.is_complete && b.is_complete) {
                    if (a.has_current_day_lock !== b.has_current_day_lock) {
                      return a.has_current_day_lock ? 1 : -1;
                    }
                  }
                  return a.display_name.localeCompare(b.display_name);
                })
                .map((user) => (
                <tr 
                  key={user.uid}
                  onClick={() => handleUserClick(user.uid)}
                  style={{ cursor: 'pointer', fontSize: '0.85rem', lineHeight: '1.2' }}
                  className="user-row"
                >
                  <td className="py-2">
                    {user.display_name}
                  </td>
                  <td className="py-2">
                    {user.total_games > 0 ? (
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
                    ) : (
                      <span className="text-muted">-</span>
                    )}
                  </td>
                  <td className="py-2">
                    <span
                      className={`badge ${user.total_games === 0 ? 'bg-secondary' : user.is_complete ? 'bg-success' : 'bg-warning'}`}
                      style={{ fontSize: '0.75rem', padding: '0.25em 0.5em' }}
                    >
                      {user.total_games === 0 ? 'No games remaining' : user.is_complete ? 'All Picks Submitted' : 'Missing Picks'}
                    </span>
                  </td>
                  <td className="py-2">
                    <span
                      className={`badge ${user.has_current_day_lock ? 'bg-success' : 'bg-danger'}`}
                      style={{ fontSize: '0.75rem', padding: '0.25em 0.5em' }}
                    >
                      {user.has_current_day_lock ? 'Submitted' : 'Unsubmitted'}
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
