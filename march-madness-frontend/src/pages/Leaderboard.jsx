import { useEffect, useState } from "react";
import axios from "axios";
import { Alert, Modal, Button, Table, Form } from "react-bootstrap";
import { API_URL } from "../config";
import { useNavigate } from "react-router-dom";

export default function Leaderboard() {
  const [leaderboard, setLeaderboard] = useState([]);
  const [error, setError] = useState(null);
  const [selectedUser, setSelectedUser] = useState(null);
  const [selectedUserFullName, setSelectedUserFullName] = useState(null);
  const [userPicks, setUserPicks] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [filter, setFilter] = useState('overall');
  const [weekOptions, setWeekOptions] = useState([]);
  const navigate = useNavigate();

  // Function to handle authentication errors
  const handleAuthError = (err) => {
    console.error('Auth check - Error:', err);
    
    // Log token information for debugging (without exposing the full token)
    const token = localStorage.getItem('token');
    console.log('Auth check - Token exists:', !!token);
    if (token) {
      console.log('Auth check - Token length:', token.length);
      console.log('Auth check - Token starts with:', token.substring(0, 10) + '...');
    }
    
    // Add detailed logging for debugging
    if (err.response) {
      console.error('Auth check - Response data:', err.response.data);
      console.error('Auth check - Response status:', err.response.status);
      console.error('Auth check - Response headers:', err.response.headers);
      
      // Handle 401 Unauthorized errors - treat ALL 401s as authentication failures
      if (err.response.status === 401) {
        // Check if message explicitly mentions token expiration, but handle all 401s the same way
        const isTokenExpired = 
          (err.response.data && 
           typeof err.response.data === 'object' &&
           err.response.data.detail && 
           typeof err.response.data.detail === 'string' &&
           err.response.data.detail.includes("Token expired"));

        // Log the token expiration evaluation
        console.log('Auth check - Is explicit token expiration message present?', isTokenExpired);
        console.log('Auth check - Error response message:', 
          err.response.data && err.response.data.detail ? err.response.data.detail : 'No detail message');
        
        // All 401 errors should redirect to login regardless of the specific message
        console.log('Auth check - 401 error, redirecting to login');
        localStorage.removeItem('token');
        navigate('/login');
        return true; // Indicate error was handled
      }
    } else {
      console.error('Auth check - No response object in error');
    }
    return false; // Error wasn't handled as auth error
  };

  useEffect(() => {
    fetchWeekOptions();
  }, []);

  useEffect(() => {
    fetchLeaderboard();
  }, [filter]);

  const fetchWeekOptions = () => {
    axios.get(`${API_URL}/leaderboard/weeks`)
      .then(res => {
        setWeekOptions(res.data.weeks);
      })
      .catch(err => {
        console.error('Failed to load week options:', err);
        // Fallback to hardcoded options if API fails
        setWeekOptions([
          { key: "overall", label: "Overall" },
          { key: "cfb_week_0", label: "CFB Week 0" },
          { key: "cfb_week_1", label: "CFB Week 1" },
          { key: "cfb_week_2_nfl_week_1", label: "CFB Week 2, NFL Week 1" },
          { key: "cfb_week_3_nfl_week_2", label: "CFB Week 3, NFL Week 2" },
          { key: "cfb_week_4_nfl_week_3", label: "CFB Week 4, NFL Week 3" },
          { key: "cfb_week_5_nfl_week_4", label: "CFB Week 5, NFL Week 4" },
          { key: "cfb_week_6_nfl_week_5", label: "CFB Week 6, NFL Week 5" },
          { key: "cfb_week_7_nfl_week_6", label: "CFB Week 7, NFL Week 6" },
          { key: "cfb_week_8_nfl_week_7", label: "CFB Week 8, NFL Week 7" },
          { key: "cfb_week_9_nfl_week_8", label: "CFB Week 9, NFL Week 8" },
          { key: "cfb_week_10_nfl_week_9", label: "CFB Week 10, NFL Week 9" },
          { key: "cfb_week_11_nfl_week_10", label: "CFB Week 11, NFL Week 10" },
          { key: "cfb_week_12_nfl_week_11", label: "CFB Week 12, NFL Week 11" },
          { key: "cfb_week_13_nfl_week_12", label: "CFB Week 13, NFL Week 12" },
          { key: "cfb_week_14_nfl_week_13", label: "CFB Week 14, NFL Week 13" },
          { key: "nfl_week_14", label: "NFL Week 14" },
          { key: "nfl_week_15", label: "NFL Week 15" },
          { key: "nfl_week_16", label: "NFL Week 16" },
          { key: "nfl_week_17", label: "NFL Week 17" },
          { key: "nfl_week_18", label: "NFL Week 18" }
        ]);
      });
  };

  const fetchLeaderboard = () => {
    // Leaderboard endpoint doesn't require authentication
    axios.get(`${API_URL}/leaderboard?filter=${filter}`)
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
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      
      const response = await axios.get(`${API_URL}/user_all_past_picks/${username}?filter=${filter}`, { headers });
      
      const userInfo = leaderboard.find(player => player.username === username);
      setSelectedUserFullName(userInfo?.full_name || username);
      
      setUserPicks({
        picks: response.data.game_picks,
        tiebreakers: response.data.tiebreaker_picks
      });
      setSelectedUser(username);
      setShowModal(true);
    } catch (err) {
      // Try to handle as auth error first
      if (!handleAuthError(err)) {
        console.error(err);
        console.log(err.response?.data || err.message);
      }
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
      <div className="d-flex justify-content-between align-items-center mb-3 mb-md-4">
        <h2 className="mb-0 text-center text-md-start">Leaderboard</h2>
        <Form.Select 
          className="w-auto" 
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          {weekOptions.map((week) => (
            <option key={week.key} value={week.key}>
              {week.label}
            </option>
          ))}
        </Form.Select>
      </div>
      
      {error && (
        <Alert variant="danger" className="mb-3 mb-md-4">
          {error}
        </Alert>
      )}
      
      {leaderboard.length === 0 && !error ? (
        <Alert variant="info">
          Loading leaderboard...
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
              No picks available for this time period
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
                          .filter(tiebreaker => {
                            // Get the start time of the tiebreaker
                            const tiebreakerDate = new Date(tiebreaker.start_time);
                            // Get 6:10 PM of the same day
                            const revealTime = new Date(tiebreakerDate);
                            revealTime.setHours(18, 10, 0, 0);
                            // Compare with current time
                            return new Date() >= revealTime;
                          })
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
