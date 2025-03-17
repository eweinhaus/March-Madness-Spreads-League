import { useEffect, useState } from "react";
import axios from "axios";
import { Container, Row, Col, Card, Button, Alert, Form } from "react-bootstrap";
import { API_URL } from "../config";

export default function Picks() {
  const [games, setGames] = useState([]);
  const [picks, setPicks] = useState({});
  const [existingPicks, setExistingPicks] = useState({});
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [tiebreakers, setTiebreakers] = useState([]);
  const [tiebreakerPicks, setTiebreakerPicks] = useState({});
  const [existingTiebreakerPicks, setExistingTiebreakerPicks] = useState({});

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
        console.log('Games data from server:', gamesRes.data);
        
        // Verify game IDs are properly formatted
        const games = gamesRes.data;
        games.forEach(game => {
          console.log(`Game ID type: ${typeof game.id}, value: ${game.id}`);
        });
        
        setGames(games);
        
        // Convert picks array to object for easier lookup
        const picksObj = {};
        picksRes.data.forEach(pick => {
          if (pick.picked_team) {
            picksObj[pick.game_id] = pick.picked_team;
          }
        });
        setExistingPicks(picksObj);

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
        console.error('Error loading data:', err);
        if (err.response) {
          console.error('Response data:', err.response.data);
          console.error('Response status:', err.response.status);
        }
        setError('Failed to load games, picks, and tiebreakers');
        setIsLoading(false);
      });
  }, []);

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
      const gamePickResponses = await Promise.all(
        Object.entries(picks).map(([gameId, pickedTeam]) => {
          // Ensure game_id is a valid integer
          const game_id = Number(gameId);
          
          if (isNaN(game_id)) {
            throw new Error(`Invalid game ID: ${gameId}`);
          }
          
          return axios.post(`${API_URL}/submit_pick`, 
            {
              game_id: game_id,
              picked_team: pickedTeam
            },
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
      const messages = [
        ...gamePickResponses.map(res => res.data.message),
        ...tiebreakerPickResponses.map(res => res.data.message)
      ].filter(Boolean).join('\n');
      
      if (messages) {
        alert(messages);
      }
      
      // Update existing picks with new picks
      setExistingPicks({ ...existingPicks, ...picks });
      setExistingTiebreakerPicks({ ...existingTiebreakerPicks, ...tiebreakerPicks });
      // Clear picks after successful submission
      setPicks({});
      setTiebreakerPicks({});
    } catch (err) {
      console.error(err);
      // Display more detailed error message if available
      if (err.response && err.response.data && err.response.data.detail) {
        setError(`Error: ${err.response.data.detail}`);
      } else if (err.message) {
        setError(`Error: ${err.message}`);
      } else {
        setError('Failed to submit picks. Please try again.');
      }
    }
  };

  const hasGameStarted = (gameDate) => {
    return new Date() >= new Date(gameDate);
  };

  const availableGames = games.filter(game => {
    // Ensure game data is valid
    if (!game || !game.game_date) {
      console.warn('Invalid game data:', game);
      return false;
    }
    return !hasGameStarted(game.game_date);
  });

  const availableTiebreakers = tiebreakers.filter(tiebreaker => {
    // Ensure tiebreaker data is valid
    if (!tiebreaker || !tiebreaker.start_time) {
      console.warn('Invalid tiebreaker data:', tiebreaker);
      return false;
    }
    return !hasGameStarted(tiebreaker.start_time) && tiebreaker.is_active;
  });

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
          {/* Combined Games & Tiebreakers Section */}
          {(availableGames.length > 0 || availableTiebreakers.length > 0) && (
            <>
              <Row className="mb-3">
              </Row>
              <Row xs={1} sm={2} lg={3} className="g-3 g-md-4">
                {/* Render game cards */}
                {availableGames.map(game => {
                  const existingPick = existingPicks[game.id];
                  const currentPick = picks[game.id];
                  const selectedTeam = currentPick || existingPick;

                  return (
                    <Col key={`game-${game.id}`}>
                      <Card className="h-100 shadow-sm">
                        <Card.Body className="d-flex flex-column">
                          <Card.Title className="d-flex justify-content-between align-items-center mb-3">
                            <span className="text-truncate me-1">{game.away_team}</span>
                            <small className="text-muted mx-1">@</small>
                            <span className="text-truncate ms-1">{game.home_team}</span>
                          </Card.Title>
                          <Card.Text className="mb-3">
                            <div className="mb-1"><strong>Spread:</strong> {game.spread > 0 ? `${game.home_team} -${game.spread}` : `${game.away_team} +${-game.spread}`}</div>
                            <div className="mb-1"><strong>Game time:</strong> {formatDateForDisplay(game.game_date)}</div>
                            {existingPick && (
                              <div className="mt-2 text-success">
                                <strong>Your pick: {existingPick}</strong>
                              </div>
                            )}
                          </Card.Text>
                          <div className="d-grid gap-2 mt-auto">
                            <Button
                              variant={selectedTeam === game.away_team ? "success" : "outline-primary"}
                              onClick={() => handlePick(game.id, game.away_team)}
                              className="py-2"
                            >
                              {game.away_team} {game.spread > 0 ? `+${game.spread}` : `+${-game.spread}`}
                            </Button>
                            <Button
                              variant={selectedTeam === game.home_team ? "success" : "outline-primary"}
                              onClick={() => handlePick(game.id, game.home_team)}
                              className="py-2"
                            >
                              {game.home_team} {game.spread > 0 ? `-${game.spread}` : `-${-game.spread}`}
                            </Button>
                          </div>
                        </Card.Body>
                      </Card>
                    </Col>
                  );
                })}

                {/* Render tiebreaker cards */}
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

          {(Object.keys(picks).length > 0 || Object.keys(tiebreakerPicks).length > 0) && (
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
