import { useEffect, useState } from "react";
import axios from "axios";
import { Alert, Card, ListGroup, Badge, Container, Spinner, Modal, Button } from "react-bootstrap";
import { API_URL } from "../config";

export default function Live() {
  const [liveGames, setLiveGames] = useState([]);
  const [liveTiebreakers, setLiveTiebreakers] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedGame, setSelectedGame] = useState(null);
  const [selectedTiebreaker, setSelectedTiebreaker] = useState(null);
  const [showGameModal, setShowGameModal] = useState(false);
  const [showTiebreakerModal, setShowTiebreakerModal] = useState(false);

  useEffect(() => {
    fetchLiveData();
  }, []);

  const fetchLiveData = () => {
    setLoading(true);
    setError(null);
    
    Promise.all([
      axios.get(`${API_URL}/live_games`),
      axios.get(`${API_URL}/live_tiebreakers`)
    ])
      .then(([gamesRes, tiebreakersRes]) => {
        setLiveGames(Array.isArray(gamesRes.data) ? gamesRes.data : []);
        setLiveTiebreakers(Array.isArray(tiebreakersRes.data) ? tiebreakersRes.data : []);
        setError(null);
      })
      .catch(err => {
        console.error(err);
        setError('Failed to load live data. Please try again.');
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
      hour12: true
    });
  };

  const handleGameClick = (game) => {
    setSelectedGame(game);
    setShowGameModal(true);
  };

  const handleTiebreakerClick = (tiebreaker) => {
    setSelectedTiebreaker(tiebreaker);
    setShowTiebreakerModal(true);
  };

  const handleCloseGameModal = () => {
    setShowGameModal(false);
    setSelectedGame(null);
  };

  const handleCloseTiebreakerModal = () => {
    setShowTiebreakerModal(false);
    setSelectedTiebreaker(null);
  };

  return (
    <Container className="my-5">
      {loading && (
        <div className="text-center">
          <Spinner animation="border" role="status">
            <span className="visually-hidden">Loading...</span>
          </Spinner>
          <p className="mt-2">Loading live data...</p>
        </div>
      )}
      
      {error && (
        <Alert variant="danger" className="mb-4">
          {error}
        </Alert>
      )}
      
      {!loading && !error && liveGames.length === 0 && liveTiebreakers.length === 0 && (
        <Alert variant="info">
          No live games or tiebreakers at the moment.
        </Alert>
      )}

      {!loading && !error && liveGames.length > 0 && (
        <>
          <h2 className="mb-4">Live Contests</h2>
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
        </>
      )}

      {!loading && !error && liveTiebreakers.length > 0 && (
        <>
          <div className="row">
            {liveTiebreakers.map((tiebreaker) => (
              <div key={tiebreaker.tiebreaker_id} className="col-12 mb-4">
                <Card 
                  onClick={() => handleTiebreakerClick(tiebreaker)}
                  style={{ cursor: 'pointer' }}
                  className="hover-shadow"
                >
                  <Card.Header>
                    <span>{tiebreaker.question}</span>
                  </Card.Header>
                  <Card.Body>
                    <Card.Text>
                      Started: {formatGameDate(tiebreaker.start_time)}
                    </Card.Text>
                    <small className="text-muted">Click to view answers</small>
                  </Card.Body>
                </Card>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Game Picks Modal */}
      <Modal show={showGameModal} onHide={handleCloseGameModal}>
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
                {pick.full_name}
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
          <Button variant="secondary" onClick={handleCloseGameModal}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Tiebreaker Modal */}
      <Modal show={showTiebreakerModal} onHide={handleCloseTiebreakerModal}>
        <Modal.Header closeButton>
          <Modal.Title>
            {selectedTiebreaker && selectedTiebreaker.question}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p>
            <strong>Started:</strong> {selectedTiebreaker && formatGameDate(selectedTiebreaker.start_time)}
          </p>
          <h6>User Answers:</h6>
          <ListGroup>
            {selectedTiebreaker?.picks && selectedTiebreaker.picks.map((pick, index) => (
              <ListGroup.Item 
                key={index}
                className="d-flex justify-content-between align-items-center"
              >
                <span>{pick.full_name}</span>
                <Badge bg="secondary">
                  {pick.answer}
                </Badge>
              </ListGroup.Item>
            ))}
            {selectedTiebreaker?.picks.length === 0 && (
              <ListGroup.Item>No answers submitted yet</ListGroup.Item>
            )}
          </ListGroup>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={handleCloseTiebreakerModal}>
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