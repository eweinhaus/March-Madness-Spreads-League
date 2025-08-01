import { useEffect, useState } from "react";
import axios from "axios";
import { Container, Row, Col, Card, Button, Alert, Form } from "react-bootstrap";
import { API_URL } from "../config";
import { useNavigate } from "react-router-dom";
import { FaLock, FaUnlock } from "react-icons/fa";

export default function Picks() {
  const [games, setGames] = useState([]);
  const [picks, setPicks] = useState({});
  const [existingPicks, setExistingPicks] = useState({});
  const [locks, setLocks] = useState({});
  const [existingLocks, setExistingLocks] = useState({});
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [tiebreakers, setTiebreakers] = useState([]);
  const [tiebreakerPicks, setTiebreakerPicks] = useState({});
  const [existingTiebreakerPicks, setExistingTiebreakerPicks] = useState({});
  const navigate = useNavigate();

  // Helper function to format date for display
  const formatDateForDisplay = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  // Function to handle authentication errors
  const handleAuthError = (err) => {
    console.error('Auth check - Error loading data:', err);
    
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
    const token = localStorage.getItem('token');
    const headers = {
      'Authorization': `Bearer ${token}`
    };

    setIsLoading(true);
    // Fetch games, existing picks, and tiebreakers
    Promise.all([
      axios.get(`${API_URL}/games`, { headers }),
      axios.get(`${API_URL}/my_picks`, { headers }),
      axios.get(`${API_URL}/tiebreakers`, { headers }),
      axios.get(`${API_URL}/my_tiebreaker_picks`, { headers })
    ])
      .then(([gamesRes, picksRes, tiebreakersRes, tiebreakerPicksRes]) => {        
        // Verify game IDs are properly formatted
        const games = gamesRes.data;
        games.forEach(game => {
        });
        
        setGames(games);
        
        // Handle the picks response (back to simple format)
        const picks = picksRes.data;
        
        // Convert picks array to object for easier lookup
        const picksObj = {};
        const locksObj = {};
        picks.forEach(pick => {
          if (pick.picked_team) {
            picksObj[pick.game_id] = pick.picked_team;
          }
          if (pick.lock) {
            locksObj[pick.game_id] = pick.lock;
          }
        });
        setExistingPicks(picksObj);
        setExistingLocks(locksObj);

        // Set tiebreakers and convert tiebreaker picks to object for easier lookup
        setTiebreakers(tiebreakersRes.data);
        const tiebreakerPicksObj = {};
        tiebreakerPicksRes.data.forEach(pick => {
          if (pick.user_answer !== null) {
            tiebreakerPicksObj[pick.tiebreaker_id] = pick.user_answer;
          }
        });
        setExistingTiebreakerPicks(tiebreakerPicksObj);
        setIsLoading(false);
      })
      .catch(err => {
        // Try to handle as auth error first
        if (!handleAuthError(err)) {
          // If not an auth error, show the general error
          setError('Failed to load games, picks, and tiebreakers');
        }
        setIsLoading(false);
      });
  }, [navigate]);

  const handlePick = (gameId, team) => {
    // Ensure gameId is stored as a string for consistency
    const gameIdStr = String(gameId);
    console.log(`Setting pick for game ID: ${gameIdStr}, team: ${team}`);
    setPicks({ ...picks, [gameIdStr]: team });
  };

  const handleTiebreakerPick = (tiebreakerId, answer, isNumeric = true) => {
    // Ensure tiebreakerId is stored as a string for consistency
    const tiebreakerIdStr = String(tiebreakerId);
    setTiebreakerPicks({ 
      ...tiebreakerPicks, 
      [tiebreakerIdStr]: isNumeric ? parseFloat(answer) : answer 
    });
  };

  const handleLockToggle = (gameId) => {
    // Ensure gameId is stored as a string for consistency
    const gameIdStr = String(gameId);
    
    // Check if this game is currently locked (either in current locks or existing locks)
    const isCurrentlyLocked = locks[gameIdStr] !== undefined ? locks[gameIdStr] : (existingLocks[gameIdStr] || false);
    
    console.log('Lock toggle for game', gameIdStr, {
      currentLocks: locks,
      existingLocks: existingLocks,
      isCurrentlyLocked
    });
    
    if (isCurrentlyLocked) {
      // If this pick is currently locked, unlock it
      console.log('Unlocking game', gameIdStr);
      setLocks(prevLocks => ({
        ...prevLocks,
        [gameIdStr]: false
      }));
    } else {
      // If this pick is not locked, lock it
      // The backend will handle unlocking other games in the same week
      console.log('Locking game', gameIdStr);
      setLocks(prevLocks => ({
        ...prevLocks,
        [gameIdStr]: true
      }));
    }
  };

  const submitPicks = async () => {
    const token = localStorage.getItem('token');
    
    try {
      // Validate game picks before submitting
      for (const [gameId, pickedTeam] of Object.entries(picks)) {
        const game_id = Number(gameId);
        if (isNaN(game_id)) {
          throw new Error(`Invalid game ID format: ${gameId}`);
        }
        
        if (!pickedTeam || typeof pickedTeam !== 'string') {
          throw new Error(`Invalid team selection for game ${gameId}: ${pickedTeam}`);
        }
      }
      
      // Submit game picks
      const gamesToSubmit = new Set([
        ...Object.keys(picks),
        ...Object.keys(locks)
      ]);
      
      console.log('Submitting games:', {
        picks: Object.keys(picks),
        locks: Object.keys(locks),
        gamesToSubmit: Array.from(gamesToSubmit)
      });
      
      const gamePickResponses = await Promise.all(
        Array.from(gamesToSubmit).map(gameId => {
          // Ensure game_id is a valid integer
          const game_id = Number(gameId);
          
          if (isNaN(game_id)) {
            throw new Error(`Invalid game ID: ${gameId}`);
          }
          
          // Get the picked team (either new pick or existing pick)
          const pickedTeam = picks[gameId] || existingPicks[gameId];
          
          if (!pickedTeam) {
            throw new Error(`No pick found for game ${gameId}`);
          }
          
          // Check if this pick is locked (only send lock changes, not current status)
          const gameIdStr = String(gameId);
          const hasLockChange = locks[gameIdStr] !== undefined;
          const isLocked = hasLockChange ? locks[gameIdStr] : (existingLocks[gameIdStr] || false);
          
          console.log(`Submitting pick for game ${gameId}:`, {
            game_id,
            picked_team: pickedTeam,
            lock: isLocked,
            isNewPick: !!picks[gameId],
            isLockChange: hasLockChange,
            existingLock: existingLocks[gameIdStr]
          });
          
          // Only send lock information if there's a lock change
          const requestData = {
            game_id: game_id,
            picked_team: pickedTeam
          };
          
          // Only include lock field if there's a lock change
          if (hasLockChange) {
            requestData.lock = isLocked;
          }
          
          return axios.post(`${API_URL}/submit_pick`, 
            requestData,
            {
              headers: {
                'Authorization': `Bearer ${token}`
              }
            }
          );
        })
      );

      // Submit tiebreaker picks
      const tiebreakerPickResponses = await Promise.all(
        Object.entries(tiebreakerPicks).map(([tiebreakerId, answer]) => {
          // Ensure tiebreaker_id is a valid integer
          const tiebreaker_id = Number(tiebreakerId);
          
          if (isNaN(tiebreaker_id)) {
            throw new Error(`Invalid tiebreaker ID: ${tiebreakerId}`);
          }
          
          return axios.post(`${API_URL}/tiebreaker_picks`,
            {
              tiebreaker_id: tiebreaker_id,
              answer: answer
            },
            {
              headers: {
                'Authorization': `Bearer ${token}`
              }
            }
          );
        })
      );
      
      // Get all success messages
      const gameMessages = gamePickResponses.map(res => res.data.message).filter(Boolean);
      const tiebreakerMessages = tiebreakerPickResponses.map(res => res.data.message).filter(Boolean);
      
      console.log('Success messages:', { gameMessages, tiebreakerMessages });
      
      // Create a single consolidated message
      let consolidatedMessage = '';
      
      if (gameMessages.length > 0) {
        // If all game messages are the same, just show one
        const uniqueGameMessages = [...new Set(gameMessages)];
        if (uniqueGameMessages.length === 1) {
          consolidatedMessage = uniqueGameMessages[0];
        } else {
          consolidatedMessage = `Updated ${gameMessages.length} picks successfully`;
        }
      }
      
      if (tiebreakerMessages.length > 0) {
        if (consolidatedMessage) {
          consolidatedMessage += '\n';
        }
        // If all tiebreaker messages are the same, just show one
        const uniqueTiebreakerMessages = [...new Set(tiebreakerMessages)];
        if (uniqueTiebreakerMessages.length === 1) {
          consolidatedMessage += uniqueTiebreakerMessages[0];
        } else {
          consolidatedMessage += `Updated ${tiebreakerMessages.length} tiebreakers successfully`;
        }
      }
      
      if (consolidatedMessage) {
        alert(consolidatedMessage);
      }
      
      // Clear error message on successful submission
      setError(null);
      
      // Update existing picks with new picks
      setExistingPicks({ ...existingPicks, ...picks });
      setExistingTiebreakerPicks({ ...existingTiebreakerPicks, ...tiebreakerPicks });
      // Update existing locks with new locks
      setExistingLocks({ ...existingLocks, ...locks });
      // Clear picks and locks after successful submission
      setPicks({});
      setTiebreakerPicks({});
      setLocks({});
    } catch (err) {
      console.error(err);
      // Try to handle auth error first
      if (!handleAuthError(err)) {
        // If not an auth error, display more detailed error message if available
        if (err.response && err.response.data && err.response.data.detail) {
          const errorMessage = err.response.data.detail;
          
          // Check if it's a lock-specific error
          if (errorMessage.includes("Cannot change lock") || errorMessage.includes("Your Locked game")) {
            setError(errorMessage); // Show the full lock error message without "Error:" prefix
            setLocks({}); // Clear lock state
            console.log('Lock error detected, cleared lock state. Current state:', {
              picks: Object.keys(picks),
              locks: {},
              tiebreakerPicks: Object.keys(tiebreakerPicks)
            });
          } else {
            setError(`Error: ${errorMessage}`);
          }
        } else if (err.message) {
          setError(`Error: ${err.message}`);
        } else {
          setError('Failed to submit picks. Please try again.');
        }
      }
    }
  };

  const hasGameStarted = (gameDate) => {
    // Use UTC comparison for consistency with backend
    const now = new Date();
    const gameTime = new Date(gameDate);
    return now.getTime() >= gameTime.getTime();
  };

  const availableGames = games.filter(game => {
    // Ensure game data is valid
    if (!game || !game.game_date) {
      console.warn('Invalid game data:', game);
      return false;
    }
    return !hasGameStarted(game.game_date);
  }).sort((a, b) => new Date(a.game_date) - new Date(b.game_date));

  const availableTiebreakers = tiebreakers.filter(tiebreaker => {
    // Ensure tiebreaker data is valid
    if (!tiebreaker || !tiebreaker.start_time) {
      console.warn('Invalid tiebreaker data:', tiebreaker);
      return false;
    }
    return !hasGameStarted(tiebreaker.start_time) && tiebreaker.is_active;
  }).sort((a, b) => new Date(a.start_time) - new Date(b.start_time));

  return (
    <Container fluid="md" className="px-2 px-md-3">
      <Row className="mb-3 mb-md-4">
        <Col>
          <h2 className="text-center text-md-start">Make Your Picks</h2>
          <p className="text-muted text-center text-md-start">Select your picks for upcoming games and answer any tiebreaker questions. All picks must be submitted before game time.</p>
        </Col>
      </Row>

      {error && (
        <Row className="mb-3 mb-md-4">
          <Col>
            <Alert variant="danger">{error}</Alert>
          </Col>
        </Row>
      )}

      {isLoading ? (
        <Row>
          <Col className="text-center">
            <div>Loading games...</div>
          </Col>
        </Row>
      ) : (availableGames.length === 0 && availableTiebreakers.length === 0) ? (
        <Row>
          <Col>
            <Alert variant="info">No available contests to pick at this time</Alert>
          </Col>
        </Row>
      ) : (
        <>
          {/* Games Section */}
          {availableGames.length > 0 && (
            <>
              <Row className="mb-3">
                <Col>
                  <h3 className="text-center text-md-start">Games</h3>
                </Col>
              </Row>
              <Row xs={1} sm={2} lg={3} className="g-3 g-md-4 mb-4">
                {availableGames.map(game => {
                  const existingPick = existingPicks[game.id];
                  const currentPick = picks[game.id];
                  const selectedTeam = currentPick || existingPick;
                  const existingLock = existingLocks[game.id];
                  const currentLock = locks[game.id];
                  const isLocked = currentLock !== undefined ? currentLock : (existingLock || false);

                  return (
                    <Col key={`game-${game.id}`}>
                      <Card className={`h-100 shadow-sm ${isLocked ? 'border-warning border-3' : 'border-3'}`} style={isLocked ? {} : {borderColor: 'transparent'}}>
                        <Card.Body className="d-flex flex-column">
                          <Card.Title className="d-flex justify-content-between align-items-center mb-3">
                            <div className="d-flex align-items-center">
                              <span className="text-truncate me-1">{game.away_team}</span>
                              <small className="text-muted mx-1">@</small>
                              <span className="text-truncate ms-1">{game.home_team}</span>
                            </div>
                            <Button
                              variant="outline-secondary"
                              size="sm"
                              onClick={() => handleLockToggle(game.id)}
                              className="p-2"
                              title={isLocked ? "Unlock pick" : "Lock pick"}
                            >
                              {isLocked ? <FaLock className="text-warning" size={16} /> : <FaUnlock className="text-muted" size={16} />}
                            </Button>
                          </Card.Title>
                          <Card.Text className="mb-3">
                            <div className="mb-1"><strong>Spread:</strong> {game.spread > 0 ? `${game.home_team} -${game.spread}` : `${game.away_team} -${Math.abs(game.spread)}`}</div>
                            <div className="mb-1"><strong>Game time:</strong> {formatDateForDisplay(game.game_date)}</div>
                            {existingPick && (
                              <div className="mt-2 text-success">
                                <strong>Your pick: {existingPick}</strong>
                                {isLocked && <span className="ms-2 text-warning"><FaLock /> Lock of the week</span>}
                              </div>
                            )}
                          </Card.Text>
                          <div className="d-grid gap-2 mt-auto">
                            <Button
                              variant={selectedTeam === game.away_team ? "success" : "outline-primary"}
                              onClick={() => handlePick(game.id, game.away_team)}
                              className="py-2"
                            >
                              {game.away_team} {game.spread > 0 ? `+${game.spread}` : `-${Math.abs(game.spread)}`}
                            </Button>
                            <Button
                              variant={selectedTeam === game.home_team ? "success" : "outline-primary"}
                              onClick={() => handlePick(game.id, game.home_team)}
                              className="py-2"
                            >
                              {game.home_team} {game.spread > 0 ? `-${game.spread}` : `+${Math.abs(game.spread)}`}
                            </Button>
                          </div>
                        </Card.Body>
                      </Card>
                    </Col>
                  );
                })}
              </Row>
            </>
          )}

          {/* Tiebreakers Section */}
          {availableTiebreakers.length > 0 && (
            <><br></br>
              <Row className="mb-3">
                <Col>
                  <h3 className="text-center text-md-start">Questions</h3>
                </Col>
              </Row>
              <Row xs={1} sm={2} lg={3} className="g-3 g-md-4">
                {availableTiebreakers.map(tiebreaker => {
                  const existingAnswer = existingTiebreakerPicks[tiebreaker.id];
                  const currentAnswer = tiebreakerPicks[tiebreaker.id];
                  const answer = currentAnswer !== undefined ? currentAnswer : existingAnswer;
                  
                  // Determine if the question likely requires a numeric or text answer
                  const isNumericQuestion = tiebreaker.question.toLowerCase().includes('how many') || 
                                           tiebreaker.question.toLowerCase().includes('score') ||
                                           tiebreaker.question.toLowerCase().includes('points') ||
                                           tiebreaker.question.toLowerCase().includes('total');

                  return (
                    <Col key={`tiebreaker-${tiebreaker.id}`}>
                      <Card className="h-100 shadow-sm">
                        <Card.Body className="d-flex flex-column">
                          <Card.Title className="mb-3">
                            {tiebreaker.question}
                          </Card.Title>
                          <Card.Text className="mb-3">
                            <div className="mb-1"><strong>Deadline:</strong> {formatDateForDisplay(tiebreaker.start_time)}</div>
                            {existingAnswer !== undefined && (
                              <div className="mt-2 text-success">
                                <strong>Your answer: {existingAnswer}</strong>
                              </div>
                            )}
                          </Card.Text>
                          <Form.Group className="mt-auto">
                            {isNumericQuestion ? (
                              <Form.Control
                                type="number"
                                step="0.1"
                                placeholder="Enter your answer"
                                value={answer !== undefined ? answer : ''}
                                onChange={(e) => handleTiebreakerPick(tiebreaker.id, e.target.value, true)}
                                className="text-center"
                              />
                            ) : (
                              <Form.Control
                                type="text"
                                placeholder="Enter your answer"
                                value={answer !== undefined ? answer : ''}
                                onChange={(e) => handleTiebreakerPick(tiebreaker.id, e.target.value, false)}
                                className="text-center"
                              />
                            )}
                          </Form.Group>
                        </Card.Body>
                      </Card>
                    </Col>
                  );
                })}
              </Row>
            </>
          )}

          {(Object.keys(picks).length > 0 || Object.keys(tiebreakerPicks).length > 0 || Object.keys(locks).length > 0) && (
            <Row className="mt-4">
              <Col className="d-flex justify-content-center">
                <Button variant="success" size="lg" onClick={submitPicks} className="px-4 py-2">
                  Submit Picks
                </Button>
              </Col>
            </Row>
          )}
        </>
      )}
    </Container>
  );
}
