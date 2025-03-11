import { useEffect, useState } from "react";
import axios from "axios";
import { Alert, Card, ListGroup, Badge, Container, Spinner, Modal, Button } from "react-bootstrap";
import { API_URL } from "../config";

export default function Live() {
  const [liveGames, setLiveGames] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedGame, setSelectedGame] = useState(null);
  const [showModal, setShowModal] = useState(false);

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
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
      timeZoneName: 'short'
    });
  };

  const handleGameClick = (game) => {
    setSelectedGame(game);
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setSelectedGame(null);
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
              <Card 
                onClick={() => handleGameClick(game)}
                style={{ cursor: 'pointer' }}
                className="hover-shadow"
              >
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
                  <small className="text-muted">Click to view picks</small>
                </Card.Body>
              </Card>
            </div>
          ))}
        </div>
      )}

      {/* Picks Modal */}
      <Modal show={showModal} onHide={handleCloseModal}>
        <Modal.Header closeButton>
          <Modal.Title>
            {selectedGame && `${selectedGame.away_team} @ ${selectedGame.home_team}`}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p>
            <strong>Game Time:</strong> {selectedGame && formatGameDate(selectedGame.game_date)}
          </p>
          <p>
            <strong>Spread:</strong>{' '}
            {selectedGame && (selectedGame.spread > 0 
              ? `${selectedGame.home_team} -${selectedGame.spread}` 
              : `${selectedGame.away_team} +${-selectedGame.spread}`)}
          </p>
          <h6>User Picks:</h6>
          <ListGroup>
            {selectedGame?.picks && selectedGame.picks.map((pick, index) => (
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
            {selectedGame?.picks.length === 0 && (
              <ListGroup.Item>No picks for this game yet</ListGroup.Item>
            )}
          </ListGroup>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={handleCloseModal}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>

      <style jsx>{`
        .hover-shadow:hover {
          box-shadow: 0 4px 8px rgba(0,0,0,0.1);
          transform: translateY(-2px);
          transition: all 0.2s ease;
        }
      `}</style>
    </Container>
  );
} 