import { useEffect, useState } from "react";
import axios from "axios";
import { Alert, Card, ListGroup, Badge, Container, Spinner } from "react-bootstrap";
import { API_URL } from "../config";

export default function Live() {
  const [liveGames, setLiveGames] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLiveGames();
  }, []);

  const fetchLiveGames = () => {
    setLoading(true);
    setError(null);
    
    axios.get(`${API_URL}/live_games`)
      .then(res => {
        setLiveGames(Array.isArray(res.data) ? res.data : []);
        setError(null);
      })
      .catch(err => {
        console.error(err);
        setError('Failed to load live games. Please try again.');
      })
      .finally(() => {
        setLoading(false);
      });
  };

  const formatGameDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  return (
    <Container className="my-5">
      <h2 className="mb-4">Live Games</h2>
      
      {loading && (
        <div className="text-center">
          <Spinner animation="border" role="status">
            <span className="visually-hidden">Loading...</span>
          </Spinner>
          <p className="mt-2">Loading live games...</p>
        </div>
      )}
      
      {error && (
        <Alert variant="danger" className="mb-4">
          {error}
        </Alert>
      )}
      
      {!loading && !error && liveGames.length === 0 && (
        <Alert variant="info">
          No live games at the moment.
        </Alert>
      )}
      
      {!loading && !error && liveGames.length > 0 && (
        <div className="row">
          {liveGames.map((game) => (
            <div key={game.game_id} className="col-12 mb-4">
              <Card>
                <Card.Header className="d-flex justify-content-between align-items-center">
                  <span>
                    {game.away_team} @ {game.home_team}
                  </span>
                  <Badge bg="primary">
                    {game.spread > 0 
                      ? `${game.home_team} -${game.spread}` 
                      : `${game.away_team} +${-game.spread}`}
                  </Badge>
                </Card.Header>
                <Card.Body>
                  <Card.Text>
                    Started: {formatGameDate(game.game_date)}
                  </Card.Text>
                  <h6>User Picks:</h6>
                  <ListGroup>
                    {game.picks && game.picks.map((pick, index) => (
                      <ListGroup.Item 
                        key={index}
                        className="d-flex justify-content-between align-items-center"
                      >
                        {pick.username}
                        <Badge bg="secondary">
                          {pick.picked_team}
                        </Badge>
                      </ListGroup.Item>
                    ))}
                  </ListGroup>
                </Card.Body>
              </Card>
            </div>
          ))}
        </div>
      )}
    </Container>
  );
} 