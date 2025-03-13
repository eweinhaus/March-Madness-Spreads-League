import { useEffect, useState } from "react";
import axios from "axios";
import { Container, Row, Col, Card, Button, Alert } from "react-bootstrap";
import { API_URL } from "../config";

export default function Picks() {
  const [games, setGames] = useState([]);
  const [picks, setPicks] = useState({});
  const [existingPicks, setExistingPicks] = useState({});
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

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
    // Fetch games and existing picks
    Promise.all([
      axios.get(`${API_URL}/games`, { headers }),
      axios.get(`${API_URL}/my_picks`, { headers })
    ])
      .then(([gamesRes, picksRes]) => {
        setGames(gamesRes.data);
        // Convert picks array to object for easier lookup
        const picksObj = {};
        picksRes.data.forEach(pick => {
          if (pick.picked_team) {
            picksObj[pick.game_id] = pick.picked_team;
          }
        });
        setExistingPicks(picksObj);
        setIsLoading(false);
      })
      .catch(err => {
        console.error(err);
        setError('Failed to load games and picks');
        setIsLoading(false);
      });
  }, []);

  const handlePick = (gameId, team) => {
    setPicks({ ...picks, [gameId]: team });
  };

  const submitPicks = async () => {
    const token = localStorage.getItem('token');
    
    try {
      const responses = await Promise.all(
        Object.entries(picks).map(([gameId, pickedTeam]) => 
          axios.post(`${API_URL}/submit_pick`, 
            {
              game_id: parseInt(gameId),
              picked_team: pickedTeam
            },
            {
              headers: {
                'Authorization': `Bearer ${token}`
              }
            }
          )
        )
      );
      
      // Get all success messages
      const messages = responses.map(res => res.data.message).join('\n');
      alert(messages);
      
      // Update existing picks with new picks
      setExistingPicks({ ...existingPicks, ...picks });
      // Clear picks after successful submission
      setPicks({});
    } catch (err) {
      console.error(err);
      setError('Failed to submit picks. Please try again.');
    }
  };

  const hasGameStarted = (gameDate) => {
    return new Date() >= new Date(gameDate);
  };

  // Get only games that haven't started yet
  const availableGames = games.filter(game => !hasGameStarted(game.game_date));

  return (
    <Container fluid="md" className="px-2 px-md-3">
      <Row className="mb-3 mb-md-4">
        <Col>
          <h2 className="text-center text-md-start">Make Your Picks</h2>
          <p className="text-muted text-center text-md-start">Select your picks for upcoming games. All picks must be submitted before game time.</p>
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
      ) : availableGames.length === 0 ? (
        <Row>
          <Col>
            <Alert variant="info">No available games to pick at this time.</Alert>
          </Col>
        </Row>
      ) : (
        <>
          <Row xs={1} sm={2} lg={3} className="g-3 g-md-4">
            {availableGames.map(game => {
              const existingPick = existingPicks[game.id];
              const currentPick = picks[game.id];
              const selectedTeam = currentPick || existingPick;

              return (
                <Col key={game.id}>
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
          </Row>

          {Object.keys(picks).length > 0 && (
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
