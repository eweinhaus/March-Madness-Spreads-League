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
              <div>
                {index + 1}. {player.full_name}
              </div>
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
              No contests available that have started.
            </Alert>
          ) : (
            <>
              {userPicks.picks && userPicks.picks.length > 0 && (
                <div className="table-responsive mb-4">
                  <Table striped bordered hover responsive className="mb-0" size="sm">
                    <thead>
                      <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
                        <th className="py-2">Game</th>
                        <th className="py-2">Pick</th>
                      </tr>
                    </thead>
                    <tbody className="small">
                      {userPicks.picks
                        .sort((a, b) => new Date(b.game_date) - new Date(a.game_date))
                        .map((pick) => {
                        // Determine row color based on result
                        let rowClass = "";
                        if (pick.winning_team && pick.winning_team !== "PUSH") {
                          rowClass = pick.winning_team === pick.picked_team ? "table-success" : "table-danger";
                        } else if (pick.winning_team === "PUSH") {
                          rowClass = "table-warning"; // Highlight PUSH rows in yellow
                        }
                        
                        return (
                          <tr key={pick.game_id} className={rowClass} style={{ fontSize: '0.85rem', lineHeight: '1.2' }}>
                            <td className="text-nowrap py-2">
                              {pick.spread < 0 
                                ? `${pick.away_team} @ ${pick.home_team} +${Math.abs(pick.spread)}` 
                                : `${pick.away_team} @ ${pick.home_team} -${pick.spread}`}
                            </td>
                            <td className="py-2">
                              {pick.picked_team}
                              {pick.winning_team === "PUSH" && (
                                <span className="ms-2 badge bg-secondary" style={{ fontSize: '0.75rem', padding: '0.2em 0.4em' }}>PUSH</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </Table>
                </div>
              )}

              {userPicks.tiebreakers && userPicks.tiebreakers.length > 0 && (
                <>
                  <div className="table-responsive">
                    <Table striped bordered hover responsive className="mb-0" size="sm">
                      <thead>
                        <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
                          <th className="py-2">Question</th>
                          <th className="py-2">Pick</th>
                        </tr>
                      </thead>
                      <tbody className="small">
                        {userPicks.tiebreakers
                          .sort((a, b) => new Date(b.start_time) - new Date(a.start_time))
                          .map((tiebreaker) => {
                          // Color code based on points awarded instead of answer correctness
                          const hasPoints = tiebreaker.points_awarded && tiebreaker.points_awarded > 0;
                          const rowClass = hasPoints ? "table-success" : "";
                          
                          return (
                            <tr key={tiebreaker.tiebreaker_id} className={rowClass} style={{ fontSize: '0.85rem', lineHeight: '1.2' }}>
                              <td className="py-2">{tiebreaker.question}</td>
                              <td className="py-2">
                                {tiebreaker.user_answer !== null && tiebreaker.user_answer !== undefined 
                                  ? tiebreaker.user_answer 
                                  : <span className="text-muted">No Answer</span>}
                                {tiebreaker.correct_answer && !["N/A", "NA", "n/a", "na", "Na"].includes(tiebreaker.correct_answer) && (
                                  <span className="text-muted ms-2" style={{ fontSize: '0.8rem' }}>
                                    (Correct: {tiebreaker.correct_answer})
                                  </span>
                                )}
                              </td>
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
