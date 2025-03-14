import { useEffect, useState } from "react";
import axios from "axios";
import { Alert, Modal, Button, Table } from "react-bootstrap";
import { API_URL } from "../config";

export default function Leaderboard() {
  const [leaderboard, setLeaderboard] = useState([]);
  const [error, setError] = useState(null);
  const [selectedUser, setSelectedUser] = useState(null);
  const [selectedUserFullName, setSelectedUserFullName] = useState(null);
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
      
      // Use the admin endpoint to get all picks for the selected user
      const response = await axios.get(`${API_URL}/admin/user_all_picks/${username}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      const userInfo = leaderboard.find(player => player.username === username);
      setSelectedUserFullName(userInfo?.full_name || username);
      
      // Filter tiebreakers to only show ones that have started
      const activeTiebreakers = response.data.tiebreaker_picks.filter(
        t => new Date(t.start_time) <= new Date()
      );
      
      // Debug logging for Ethan Weinhaus2
      if (username === "Ethan Weinhaus2" || username.includes("Weinhaus")) {
        console.log("User:", username);
        console.log("Response data:", JSON.stringify(response.data, null, 2));
        console.log("Tiebreakers data:", JSON.stringify(activeTiebreakers, null, 2));
      }
      
      setUserPicks({
        picks: response.data.game_picks.filter(game => new Date(game.game_date) <= new Date()),
        tiebreakers: activeTiebreakers
      });
      setSelectedUser(username);
      setShowModal(true);
    } catch (err) {
      console.error(err);
      //Log error in console
      console.log(err.response?.data || err.message);
    }
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setSelectedUser(null);
    setSelectedUserFullName(null);
    setUserPicks([]);
  };

  return (
    <div className="container my-3 my-md-5 px-2 px-md-3">
      <h2 className="mb-3 mb-md-4 text-center text-md-start">Leaderboard</h2>
      
      {error && (
        <Alert variant="danger" className="mb-3 mb-md-4">
          {error}
        </Alert>
      )}
      
      {leaderboard.length === 0 && !error ? (
        <Alert variant="info">
          No entries in the leaderboard yet.
        </Alert>
      ) : (
        <ul className="list-group shadow-sm">
          {leaderboard.map((player, index) => (
            <li 
              key={player.username} 
              className="list-group-item d-flex justify-content-between align-items-center py-3"
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

      <Modal show={showModal} onHide={handleCloseModal} size="lg" centered fullscreen="sm-down">
        <Modal.Header closeButton>
          <Modal.Title>{selectedUserFullName}'s Picks</Modal.Title>
        </Modal.Header>
        <Modal.Body className="p-2 p-md-3">
          {(!userPicks.picks || userPicks.picks.length === 0) && (!userPicks.tiebreakers || userPicks.tiebreakers.length === 0) ? (
            <Alert variant="info">
              No picks available for games or tiebreakers that have started.
            </Alert>
          ) : (
            <>
              {userPicks.picks && userPicks.picks.length > 0 && (
                <div className="table-responsive mb-4">
                  <Table striped bordered hover responsive className="mb-0">
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
                      {userPicks.picks.map((pick) => (
                        <tr key={pick.game_id}>
                          <td className="text-nowrap">{pick.away_team} @ {pick.home_team}</td>
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
                                : `${pick.winning_team}`
                              : "Pending"}
                          </td>
                          <td className="text-center">{pick.points_awarded}</td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              )}

              {userPicks.tiebreakers && userPicks.tiebreakers.length > 0 && (
                <>
                  <div className="table-responsive">
                    <Table striped bordered hover responsive className="mb-0">
                      <thead>
                        <tr>
                          <th>Question</th>
                          <th>Pick</th>
                          <th>Correct Answer</th>
                        </tr>
                      </thead>
                      <tbody>
                        {userPicks.tiebreakers.map((tiebreaker) => {
                          return (
                            <tr key={tiebreaker.tiebreaker_id}>
                              <td>{tiebreaker.question}</td>
                              <td>
                                {tiebreaker.user_answer !== null && tiebreaker.user_answer !== undefined 
                                  ? tiebreaker.user_answer 
                                  : <span className="text-muted">No Answer</span>}
                              </td>
                              <td>{tiebreaker.correct_answer || 'Pending'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </Table>
                  </div>
                </>
              )}
            </>
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
