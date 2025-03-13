import { useEffect, useState } from "react";
import axios from "axios";
import { Alert, Modal, Button, Table } from "react-bootstrap";
import { API_URL } from "../config";

export default function Leaderboard() {
  const [leaderboard, setLeaderboard] = useState([]);
  const [error, setError] = useState(null);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userPicks, setUserPicks] = useState([]);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    fetchLeaderboard();
  }, []);

  const fetchLeaderboard = () => {
    axios.get(`${API_URL}/leaderboard`)
      .then(res => {
        setLeaderboard(res.data);
        setError(null);
      })
      .catch(err => {
        console.error(err);
        setError('Failed to load leaderboard. Please try again.');
      });
  };

  const handleUserClick = async (username) => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API_URL}/user_picks/${username}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      setUserPicks(response.data);
      setSelectedUser(username);
      setShowModal(true);
    } catch (err) {
      console.error(err);
      setError('Failed to load user picks');
    }
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setSelectedUser(null);
    setUserPicks([]);
  };

  return (
    <div className="container my-5">
      <h2 className="mb-4">Leaderboard</h2>
      
      {error && (
        <Alert variant="danger" className="mb-4">
          {error}
        </Alert>
      )}
      
      {leaderboard.length === 0 && !error ? (
        <Alert variant="info">
          No entries in the leaderboard yet.
        </Alert>
      ) : (
        <ul className="list-group">
          {leaderboard.map((player, index) => (
            <li 
              key={player.username} 
              className="list-group-item d-flex justify-content-between align-items-center"
              style={{ cursor: 'pointer' }}
              onClick={() => handleUserClick(player.username)}
            >
              {index + 1}. {player.full_name}
              <span className="badge bg-primary rounded-pill">
                {player.total_points} points
              </span>
            </li>
          ))}
        </ul>
      )}

      <Modal show={showModal} onHide={handleCloseModal} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>{selectedUser}'s Picks</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {userPicks.length === 0 ? (
            <Alert variant="info">
              No picks available for games that have started.
            </Alert>
          ) : (
            <Table striped bordered hover>
              <thead>
                <tr>
                  <th>Game</th>
                  <th>Spread</th>
                  <th>Pick</th>
                  <th>Result</th>
                  <th>Points</th>
                </tr>
              </thead>
              <tbody>
                {userPicks.map((pick) => (
                  <tr key={pick.game_id}>
                    <td>{pick.away_team} @ {pick.home_team}</td>
                    <td>
                      {pick.spread > 0 
                        ? `${pick.home_team} -${pick.spread}` 
                        : `${pick.away_team} +${-pick.spread}`}
                    </td>
                    <td>{pick.picked_team}</td>
                    <td>
                      {pick.winning_team 
                        ? pick.winning_team === "PUSH"
                          ? "PUSH"
                          : `Covered: ${pick.winning_team}`
                        : "Pending"}
                    </td>
                    <td>{pick.points_awarded}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={handleCloseModal}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}
