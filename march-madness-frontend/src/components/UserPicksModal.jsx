import React, { useState } from 'react';
import { Modal, Table, Badge, Tabs, Tab, Form, Button } from 'react-bootstrap';
import { FaLock } from 'react-icons/fa';
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
    // Game result badge only
    if (!pick.picked_team) {
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
            <Table striped bordered hover responsive size="sm">
              <thead>
                <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
                  <th className="py-2">Game Date</th>
                  <th className="py-2">Matchup</th>
                  <th className="py-2">Pick</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody className="small">
                {game_picks
                  ?.sort((a, b) => new Date(b.game_date) - new Date(a.game_date))
                  .map((game) => (
                  <tr key={game.game_id} style={{ fontSize: '0.85rem', lineHeight: '1.2' }}>
                    <td className="py-2">{formatDate(game.game_date)}</td>
                    <td className="py-2 text-nowrap">
                      {game.spread < 0 
                        ? `${game.away_team} @ ${game.home_team} +${Math.abs(game.spread)}` 
                        : `${game.away_team} @ ${game.home_team} -${game.spread}`}
                    </td>
                    <td className="py-2">
                      <div className="d-flex align-items-center">
                        {game.picked_team || <span className="text-muted">-</span>}
                        {game.picked_team && game.lock && (
                          <FaLock className="ms-1 text-black" size={12} />
                        )}
                      </div>
                    </td>
                    <td className="py-2">
                      {getStatusBadge(game, game)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Tab>
          <Tab eventKey="tiebreakers" title="Question Picks">
            <Table striped bordered hover responsive size="sm">
              <thead>
                <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
                  <th className="py-2">Start Time</th>
                  <th className="py-2">Question</th>
                  <th className="py-2">Answer</th>
                  {isAdmin && <th className="py-2">Points</th>}
                </tr>
              </thead>
              <tbody className="small">
                {tiebreaker_picks
                  ?.sort((a, b) => new Date(b.start_time) - new Date(a.start_time))
                  .map((tiebreaker) => (
                  <tr key={tiebreaker.tiebreaker_id} style={{ fontSize: '0.85rem', lineHeight: '1.2' }}>
                    <td className="py-2">{formatDate(tiebreaker.start_time)}</td>
                    <td className="py-2">{tiebreaker.question}</td>
                    <td className="py-2">
                      {tiebreaker.user_answer || <span className="text-muted">-</span>}
                      {tiebreaker.correct_answer && (
                        <span className="text-muted ms-2" style={{ fontSize: '0.8rem' }}>
                          (Correct: {tiebreaker.correct_answer})
                        </span>
                      )}
                    </td>
                    {isAdmin && (
                      <td className="py-2">
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