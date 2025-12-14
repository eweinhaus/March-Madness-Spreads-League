import { useEffect, useState } from "react";
import axios from "axios";
import { Alert, Modal, Button, Table, Form, Accordion } from "react-bootstrap";
import { FaLock } from "react-icons/fa";
import { API_URL } from "../config";
import { useNavigate } from "react-router-dom";

export default function Leaderboard() {
  const [leaderboard, setLeaderboard] = useState([]);
  const [error, setError] = useState(null);
  
  // Debug environment information
  console.log('=== LEADERBOARD DEBUG INFO ===');
  console.log('Environment MODE:', import.meta.env.MODE);
  console.log('Environment DEV:', import.meta.env.DEV);
  console.log('Environment PROD:', import.meta.env.PROD);
  console.log('API_URL from config:', API_URL);
  console.log('Current window.location:', window.location.href);
  console.log('User Agent:', navigator.userAgent);
  console.log('================================');
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
    
    // Test simple endpoint first
    console.log('Testing simple health endpoint...');
    axios.get(`${API_URL}/health`)
      .then(res => {
        console.log('Health check successful:', res.data);
      })
      .catch(err => {
        console.error('Health check failed:', err);
      });
      
    // Test CORS endpoint
    console.log('Testing CORS endpoint...');
    axios.get(`${API_URL}/test-cors`)
      .then(res => {
        console.log('CORS test successful:', res.data);
      })
      .catch(err => {
        console.error('CORS test failed:', err);
      });
      
    // Test simple leaderboard endpoint
    console.log('Testing simple leaderboard endpoint...');
    axios.get(`${API_URL}/test-leaderboard`)
      .then(res => {
        console.log('Test leaderboard successful:', res.data);
      })
      .catch(err => {
        console.error('Test leaderboard failed:', err);
      });
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
    console.log('Fetching leaderboard with API_URL:', API_URL);
    console.log('Filter:', filter);
    console.log('Full URL:', `${API_URL}/leaderboard?filter=${filter}`);
    
    // Leaderboard endpoint doesn't require authentication
    axios.get(`${API_URL}/leaderboard?filter=${filter}`)
      .then(res => {
        console.log('Leaderboard response received:', res);
        console.log('Response status:', res.status);
        console.log('Response data type:', typeof res.data);
        console.log('Response data length:', Array.isArray(res.data) ? res.data.length : 'Not an array');
        console.log('First item:', res.data?.[0]);
        
        setLeaderboard(res.data);
        setError(null);
      })
      .catch(err => {
        console.error('Leaderboard fetch error details:');
        console.error('Error object:', err);
        console.error('Error message:', err.message);
        console.error('Error code:', err.code);
        
        if (err.response) {
          console.error('Response status:', err.response.status);
          console.error('Response data:', err.response.data);
          console.error('Response headers:', err.response.headers);
        } else if (err.request) {
          console.error('Request made but no response received:', err.request);
        } else {
          console.error('Error setting up request:', err.message);
        }
        
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
        // Check for permission error (user doesn't have make_picks permission)
        if (err.response && err.response.status === 404) {
          console.log('User not found or does not have permission to make picks');
          // Don't show error to user, just silently fail
        } else {
          console.error(err);
          console.log(err.response?.data || err.message);
        }
      }
    }
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setSelectedUser(null);
    setSelectedUserFullName(null);
    setUserPicks([]);
  };

  const groupPicksByWeek = (picks) => {
    const weekRanges = {
      "cfb_week_0": {"start": "2025-08-19T07:00:00Z", "end": "2025-08-26T06:59:59Z", "label": "CFB Week 0"},
      "cfb_week_1": {"start": "2025-08-26T07:00:00Z", "end": "2025-09-02T06:59:59Z", "label": "CFB Week 1"},
      "cfb_week_2_nfl_week_1": {"start": "2025-09-02T07:00:00Z", "end": "2025-09-09T06:59:59Z", "label": "CFB Week 2, NFL Week 1"},
      "cfb_week_3_nfl_week_2": {"start": "2025-09-09T07:00:00Z", "end": "2025-09-16T06:59:59Z", "label": "CFB Week 3, NFL Week 2"},
      "cfb_week_4_nfl_week_3": {"start": "2025-09-16T07:00:00Z", "end": "2025-09-23T06:59:59Z", "label": "CFB Week 4, NFL Week 3"},
      "cfb_week_5_nfl_week_4": {"start": "2025-09-23T07:00:00Z", "end": "2025-09-30T06:59:59Z", "label": "CFB Week 5, NFL Week 4"},
      "cfb_week_6_nfl_week_5": {"start": "2025-09-30T07:00:00Z", "end": "2025-10-07T06:59:59Z", "label": "CFB Week 6, NFL Week 5"},
      "cfb_week_7_nfl_week_6": {"start": "2025-10-07T07:00:00Z", "end": "2025-10-14T06:59:59Z", "label": "CFB Week 7, NFL Week 6"},
      "cfb_week_8_nfl_week_7": {"start": "2025-10-14T07:00:00Z", "end": "2025-10-21T06:59:59Z", "label": "CFB Week 8, NFL Week 7"},
      "cfb_week_9_nfl_week_8": {"start": "2025-10-21T07:00:00Z", "end": "2025-10-28T06:59:59Z", "label": "CFB Week 9, NFL Week 8"},
      "cfb_week_10_nfl_week_9": {"start": "2025-10-28T07:00:00Z", "end": "2025-11-04T06:59:59Z", "label": "CFB Week 10, NFL Week 9"},
      "cfb_week_11_nfl_week_10": {"start": "2025-11-04T07:00:00Z", "end": "2025-11-11T06:59:59Z", "label": "CFB Week 11, NFL Week 10"},
      "cfb_week_12_nfl_week_11": {"start": "2025-11-11T07:00:00Z", "end": "2025-11-18T06:59:59Z", "label": "CFB Week 12, NFL Week 11"},
      "cfb_week_13_nfl_week_12": {"start": "2025-11-18T07:00:00Z", "end": "2025-11-25T06:59:59Z", "label": "CFB Week 13, NFL Week 12"},
      "cfb_week_14_nfl_week_13": {"start": "2025-11-25T07:00:00Z", "end": "2025-12-02T06:59:59Z", "label": "CFB Week 14, NFL Week 13"},
      "nfl_week_14": {"start": "2025-12-02T07:00:00Z", "end": "2025-12-09T06:59:59Z", "label": "NFL Week 14"},
      "nfl_week_15": {"start": "2025-12-09T07:00:00Z", "end": "2025-12-16T06:59:59Z", "label": "NFL Week 15"},
      "nfl_week_16": {"start": "2025-12-16T07:00:00Z", "end": "2025-12-23T06:59:59Z", "label": "NFL Week 16"},
      "nfl_week_17": {"start": "2025-12-23T07:00:00Z", "end": "2025-12-30T06:59:59Z", "label": "NFL Week 17"},
      "nfl_week_18": {"start": "2025-12-30T07:00:00Z", "end": "2026-01-06T06:59:59Z", "label": "NFL Week 18"}
    };

    const groupedPicks = {};

    picks.forEach(pick => {
      const gameDate = new Date(pick.game_date);

      // Find which week this game belongs to
      for (const [weekKey, weekInfo] of Object.entries(weekRanges)) {
        const weekStart = new Date(weekInfo.start);
        const weekEnd = new Date(weekInfo.end);

        if (gameDate >= weekStart && gameDate <= weekEnd) {
          if (!groupedPicks[weekKey]) {
            groupedPicks[weekKey] = {
              label: weekInfo.label,
              picks: []
            };
          }
          groupedPicks[weekKey].picks.push(pick);
          break;
        }
      }
    });

    return groupedPicks;
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
              <div className="d-flex align-items-center gap-2">
                <span className="badge bg-primary rounded-pill">
                  {player.total_points} points
                </span>
                <span className="badge bg-warning text-dark rounded-pill d-flex align-items-center gap-1" style={{ fontSize: '0.75rem' }}>
                  {player.correct_locks} <FaLock className="text-dark" size={10} />
                  </span>
                {filter !== 'overall' && player.first_tiebreaker_diff !== 999999 && (
                  <span className="badge bg-info rounded-pill" style={{ fontSize: '0.75rem' }}>
                    TB1: {player.first_tiebreaker_diff}
                  </span>
                )}
              </div>
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
                <>
                  {filter === 'overall' ? (
                    // Show accordions for each week when viewing overall
                    <Accordion defaultActiveKey="" className="mb-4">
                      {Object.entries(groupPicksByWeek(userPicks.picks))
                        .sort(([a], [b]) => {
                          // Sort weeks reverse chronologically (most recent first)
                          const weekOrder = Object.keys({
                            "cfb_week_0": 0,
                            "cfb_week_1": 1,
                            "cfb_week_2_nfl_week_1": 2,
                            "cfb_week_3_nfl_week_2": 3,
                            "cfb_week_4_nfl_week_3": 4,
                            "cfb_week_5_nfl_week_4": 5,
                            "cfb_week_6_nfl_week_5": 6,
                            "cfb_week_7_nfl_week_6": 7,
                            "cfb_week_8_nfl_week_7": 8,
                            "cfb_week_9_nfl_week_8": 9,
                            "cfb_week_10_nfl_week_9": 10,
                            "cfb_week_11_nfl_week_10": 11,
                            "cfb_week_12_nfl_week_11": 12,
                            "cfb_week_13_nfl_week_12": 13,
                            "cfb_week_14_nfl_week_13": 14,
                            "nfl_week_14": 15,
                            "nfl_week_15": 16,
                            "nfl_week_16": 17,
                            "nfl_week_17": 18,
                            "nfl_week_18": 19
                          });
                          return weekOrder.indexOf(b) - weekOrder.indexOf(a); // Reverse for most recent first
                        })
                        .map(([weekKey, weekData], index) => (
                          <Accordion.Item key={weekKey} eventKey={weekKey}>
                            <Accordion.Header>
                              {weekData.label} ({weekData.picks.length} pick{weekData.picks.length !== 1 ? 's' : ''})
                            </Accordion.Header>
                            <Accordion.Body className="p-2">
                              <div className="table-responsive">
                                <Table striped bordered hover responsive className="mb-0" size="sm">
                                  <thead>
                                    <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
                                      <th className="py-2">Game</th>
                                      <th className="py-2">Pick</th>
                                    </tr>
                                  </thead>
                                  <tbody className="small">
                                    {weekData.picks
                                      .sort((a, b) => new Date(b.game_date) - new Date(a.game_date))
                                      .map((pick) => {
                                        // Determine background color for pick column based on result
                                        let pickCellClass = "";
                                        if (pick.winning_team && pick.winning_team !== "PUSH") {
                                          // Normalize team names for comparison (remove trailing spaces and asterisks)
                                          const normalizeTeamName = (name) => name?.replace(/[\s*]+$/, '');
                                          const isCorrectPick = normalizeTeamName(pick.winning_team) === normalizeTeamName(pick.picked_team);
                                          pickCellClass = isCorrectPick ? "table-success" : "table-danger";
                                        } else if (pick.winning_team === "PUSH") {
                                          pickCellClass = "table-warning"; // Highlight PUSH picks in yellow
                                        }

                                        return (
                                          <tr key={pick.game_id} style={{ fontSize: '0.85rem', lineHeight: '1.2' }}>
                                            <td className="text-nowrap py-2">
                                              {pick.spread < 0
                                                ? `${pick.away_team} @ ${pick.home_team} +${Math.abs(pick.spread)}`
                                                : `${pick.away_team} @ ${pick.home_team} -${pick.spread}`}
                                            </td>
                                            <td className={`py-2 ${pickCellClass}`} style={{
                                              ...(pick.lock && {
                                                border: `3px solid ${
                                                  !pick.winning_team || pick.winning_team === ''
                                                    ? '#000000' // Black for unresolved games
                                                    : (() => {
                                                        if (pick.winning_team === "PUSH") return '#8B0000'; // Dark red for push
                                                        const normalizeTeamName = (name) => name?.replace(/[\s*]+$/, '');
                                                        const isCorrectPick = normalizeTeamName(pick.winning_team) === normalizeTeamName(pick.picked_team);
                                                        return isCorrectPick ? '#006400' : '#8B0000'; // Dark green for correct, dark red for incorrect
                                                      })()
                                                }`,
                                                borderRadius: '6px',
                                                position: 'relative'
                                              })
                                            }}>
                                              <div className="d-flex align-items-center gap-2">
                                                {!pick.picked_team ? <span className="fst-italic text-muted">No pick submitted</span> :
                                                  (() => {
                                                    // Normalize team names for comparison (remove trailing spaces and asterisks) - v2
                                                    const normalizeTeamName = (name) => name?.replace(/[\s*]+$/, '');
                                                    const isHomeTeam = normalizeTeamName(pick.picked_team) === normalizeTeamName(pick.home_team);

                                                    return isHomeTeam
                                                      ? `${pick.picked_team} ${pick.spread < 0 ? `+${Math.abs(pick.spread)}` : `-${pick.spread}`}`
                                                      : `${pick.picked_team} ${pick.spread < 0 ? `-${Math.abs(pick.spread)}` : `+${pick.spread}`}`
                                                  })()
                                                }
                                                {pick.lock && (
                                                  <FaLock className="text-dark" size={14} title="Lock of the Week" />
                                                )}
                                                {pick.winning_team === "PUSH" && (
                                                  <span className="badge bg-secondary" style={{ fontSize: '0.75rem', padding: '0.2em 0.4em' }}>PUSH</span>
                                                )}
                                              </div>
                                            </td>
                                          </tr>
                                        );
                                      })}
                                  </tbody>
                                </Table>
                              </div>
                            </Accordion.Body>
                          </Accordion.Item>
                        ))}

                        {/* Questions accordion at the bottom */}
                        {userPicks.tiebreakers && userPicks.tiebreakers.length > 0 && (
                          <Accordion.Item eventKey="questions">
                            <Accordion.Header>
                              Questions ({userPicks.tiebreakers.length} answer{userPicks.tiebreakers.length !== 1 ? 's' : ''})
                            </Accordion.Header>
                            <Accordion.Body className="p-2">
                              <div className="table-responsive">
                                <Table striped bordered hover responsive className="mb-0" size="sm">
                                  <thead>
                                    <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
                                      <th className="py-2">Question</th>
                                      <th className="py-2">Pick</th>
                                      <th className="py-2">Accuracy</th>
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
                                          <td className="py-2 text-center">
                                            {tiebreaker.accuracy_diff !== null ? (
                                              <span className="badge bg-info" style={{ fontSize: '0.75rem', padding: '0.2em 0.4em' }}>
                                                {tiebreaker.accuracy_diff}
                                              </span>
                                            ) : (
                                              <span className="text-muted" style={{ fontSize: '0.75rem' }}>-</span>
                                            )}
                                          </td>
                                        </tr>
                                      );
                                    })}
                                  </tbody>
                                </Table>
                              </div>
                            </Accordion.Body>
                          </Accordion.Item>
                        )}
                    </Accordion>
                  ) : (
                    // Show regular table for specific week views
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

                            // Determine background color for pick column based on result
                            let pickCellClass = "";
                            if (pick.winning_team && pick.winning_team !== "PUSH") {
                              // Normalize team names for comparison (remove trailing spaces and asterisks)
                              const normalizeTeamName = (name) => name?.replace(/[\s*]+$/, '');
                              const isCorrectPick = normalizeTeamName(pick.winning_team) === normalizeTeamName(pick.picked_team);
                              pickCellClass = isCorrectPick ? "table-success" : "table-danger";
                            } else if (pick.winning_team === "PUSH") {
                              pickCellClass = "table-warning"; // Highlight PUSH picks in yellow
                            }

                            return (
                              <tr key={pick.game_id} style={{ fontSize: '0.85rem', lineHeight: '1.2' }}>
                                <td className="text-nowrap py-2">
                                  {pick.spread < 0
                                    ? `${pick.away_team} @ ${pick.home_team} +${Math.abs(pick.spread)}`
                                    : `${pick.away_team} @ ${pick.home_team} -${pick.spread}`}
                                </td>
                                <td className={`py-2 ${pickCellClass}`} style={{
                                  ...(pick.lock && {
                                    border: `3px solid ${
                                      !pick.winning_team || pick.winning_team === ''
                                        ? '#000000' // Black for unresolved games
                                        : (() => {
                                            if (pick.winning_team === "PUSH") return '#8B0000'; // Dark red for push
                                            const normalizeTeamName = (name) => name?.replace(/[\s*]+$/, '');
                                            const isCorrectPick = normalizeTeamName(pick.winning_team) === normalizeTeamName(pick.picked_team);
                                            return isCorrectPick ? '#006400' : '#8B0000'; // Dark green for correct, dark red for incorrect
                                          })()
                                    }`,
                                    borderRadius: '6px',
                                    position: 'relative'
                                  })
                                }}>
                                  <div className="d-flex align-items-center gap-2">
                                    {!pick.picked_team ? <span className="fst-italic text-muted">No pick submitted</span> :
                                      (() => {


                                        // Normalize team names for comparison (remove trailing spaces and asterisks) - v2
                                        const normalizeTeamName = (name) => name?.replace(/[\s*]+$/, '');
                                        const isHomeTeam = normalizeTeamName(pick.picked_team) === normalizeTeamName(pick.home_team);

                                        return isHomeTeam
                                          ? `${pick.picked_team} ${pick.spread < 0 ? `+${Math.abs(pick.spread)}` : `-${pick.spread}`}`
                                          : `${pick.picked_team} ${pick.spread < 0 ? `-${Math.abs(pick.spread)}` : `+${pick.spread}`}`
                                      })()
                                    }
                                    {pick.lock && (
                                      <FaLock className="text-dark" size={14} title="Lock of the Week" />
                                    )}
                                  {pick.winning_team === "PUSH" && (
                                      <span className="badge bg-secondary" style={{ fontSize: '0.75rem', padding: '0.2em 0.4em' }}>PUSH</span>
                                  )}
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </Table>
                    </div>
                  )}
                </>
              )}

              {filter !== 'overall' && userPicks.tiebreakers && userPicks.tiebreakers.length > 0 && (
                <>
                  <div className="table-responsive">
                    <Table striped bordered hover responsive className="mb-0" size="sm">
                      <thead>
                                              <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
                        <th className="py-2">Question</th>
                        <th className="py-2">Pick</th>
                        <th className="py-2">Accuracy</th>
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
                              <td className="py-2 text-center">
                                {tiebreaker.accuracy_diff !== null ? (
                                  <span className="badge bg-info" style={{ fontSize: '0.75rem', padding: '0.2em 0.4em' }}>
                                    {tiebreaker.accuracy_diff}
                                  </span>
                                ) : (
                                  <span className="text-muted" style={{ fontSize: '0.75rem' }}>-</span>
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
