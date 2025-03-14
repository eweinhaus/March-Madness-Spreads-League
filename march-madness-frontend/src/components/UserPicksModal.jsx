import React, { useState } from 'react';
import { Modal, Table, Badge, Tabs, Tab, Form, Button } from 'react-bootstrap';
import { format } from 'date-fns';
import axios from 'axios';
import { API_URL } from '../config';

const UserPicksModal = ({ show, onHide, userPicks, isAdmin = false }) => {
  if (!userPicks) return null;

  const { user, game_picks, tiebreaker_picks } = userPicks;
  const [tiebreakerPoints, setTiebreakerPoints] = useState({});
  const [savingPoints, setSavingPoints] = useState(false);
  const [pointsError, setPointsError] = useState(null);
  const [pointsSuccess, setPointsSuccess] = useState(null);

  const formatDate = (dateString) => {
    return format(new Date(dateString), 'MMM d, yyyy h:mm a');
  };

  const getStatusBadge = (pick, game) => {
    if (!pick) {
      return <Badge bg="warning">No Pick</Badge>;
    }
    if (!game.winning_team) {
      return <Badge bg="info">Pending</Badge>;
    }
    if (game.winning_team === "PUSH") {
      return <Badge bg="secondary">Push</Badge>;
    }
    return pick.points_awarded > 0 ? 
      <Badge bg="success">Won</Badge> : 
      <Badge bg="danger">Lost</Badge>;
  };

  const handlePointsChange = (tiebreakerID, points) => {
    setTiebreakerPoints({
      ...tiebreakerPoints,
      [tiebreakerID]: points
    });
  };

  const savePoints = async (tiebreakerID, userID) => {
    if (!tiebreakerPoints[tiebreakerID] && tiebreakerPoints[tiebreakerID] !== 0) {
      return;
    }

    setPointsError(null);
    setPointsSuccess(null);
    setSavingPoints(true);

    try {
      const token = localStorage.getItem('token');
      const response = await axios.put(
        `${API_URL}/tiebreaker_picks/points`,
        {
          user_id: userID,
          tiebreaker_id: tiebreakerID,
          points: parseInt(tiebreakerPoints[tiebreakerID], 10)
        },
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      setPointsSuccess(`Points updated successfully for ${user?.full_name}`);
      // Update the points in the UI
      const updatedTiebreaker = tiebreaker_picks.find(tb => tb.tiebreaker_id === tiebreakerID);
      if (updatedTiebreaker) {
        updatedTiebreaker.points_awarded = parseInt(tiebreakerPoints[tiebreakerID], 10);
      }
    } catch (err) {
      console.error('Error updating points:', err);
      setPointsError('Failed to update points. Please try again.');
    } finally {
      setSavingPoints(false);
    }
  };

  return (
    <Modal show={show} onHide={onHide} size="lg">
      <Modal.Header closeButton>
        <Modal.Title>Picks for {user?.full_name}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {pointsError && <div className="alert alert-danger">{pointsError}</div>}
        {pointsSuccess && <div className="alert alert-success">{pointsSuccess}</div>}
        
        <Tabs defaultActiveKey="games" className="mb-3">
          <Tab eventKey="games" title="Game Picks">
            <Table striped bordered hover responsive>
              <thead>
                <tr>
                  <th>Game Date</th>
                  <th>Matchup</th>
                  <th>Spread</th>
                  <th>Pick</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {game_picks?.map((game) => (
                  <tr key={game.game_id}>
                    <td>{formatDate(game.game_date)}</td>
                    <td>{game.away_team} @ {game.home_team}</td>
                    <td>{game.spread}</td>
                    <td>
                      {game.picked_team || <span className="text-muted">-</span>}
                    </td>
                    <td>
                      {getStatusBadge(game.picked_team, game)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Tab>
          <Tab eventKey="tiebreakers" title="Question Picks">
            <Table striped bordered hover responsive>
              <thead>
                <tr>
                  <th>Start Time</th>
                  <th>Question</th>
                  <th>Answer</th>
                  {isAdmin && <th>Points</th>}
                </tr>
              </thead>
              <tbody>
                {tiebreaker_picks?.map((tiebreaker) => (
                  <tr key={tiebreaker.tiebreaker_id}>
                    <td>{formatDate(tiebreaker.start_time)}</td>
                    <td>{tiebreaker.question}</td>
                    <td>
                      {tiebreaker.user_answer || <span className="text-muted">-</span>}
                      {tiebreaker.correct_answer && (
                        <span className="text-muted ms-2">
                          (Correct: {tiebreaker.correct_answer})
                        </span>
                      )}
                    </td>
                    {isAdmin && (
                      <td>
                        <div className="d-flex align-items-center">
                          <Form.Control
                            type="number"
                            min="0"
                            value={tiebreakerPoints[tiebreaker.tiebreaker_id] !== undefined ? 
                              tiebreakerPoints[tiebreaker.tiebreaker_id] : 
                              tiebreaker.points_awarded || 0}
                            onChange={(e) => handlePointsChange(tiebreaker.tiebreaker_id, e.target.value)}
                            style={{ width: '70px' }}
                            className="me-2"
                          />
                          <Button 
                            variant="primary" 
                            size="sm"
                            disabled={savingPoints}
                            onClick={() => savePoints(tiebreaker.tiebreaker_id, user.id)}
                          >
                            Save
                          </Button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </Table>
          </Tab>
        </Tabs>
      </Modal.Body>
    </Modal>
  );
};

export default UserPicksModal; 