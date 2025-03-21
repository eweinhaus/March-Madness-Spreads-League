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
  const [showAwayPicks, setShowAwayPicks] = useState(false);
  const [showHomePicks, setShowHomePicks] = useState(false);

  useEffect(() => {
    fetchLiveData();
  }, []);

  const fetchLiveData = () => {
    setLoading(true);
    setError(null);
    console.log("Current User Time: ", new Date().toLocaleString());
    
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
      
      {!loading && !error && (
        <>
          <h2 className="mb-4">Live Contests</h2>
          {!loading && !error && liveGames.length === 0 && liveTiebreakers.length === 0 && (
            <Alert variant="info">
              No live contests at the moment.
            </Alert>
          )}
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
                      Started: {formatGameDate(game.game_date)}
                    </span>
                    <Badge bg="primary">
                      Spread: {game.spread > 0 
                        ? `${game.home_team} -${game.spread}` 
                        : `${game.away_team} -${-game.spread}`}
                    </Badge>
                  </Card.Header>
                  <Card.Body>
                    <Card.Text>
                      <span>
                      {game.away_team} @ {game.home_team}
                      </span>
                    </Card.Text>
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
                    <span>
                      Started: {formatGameDate(tiebreaker.start_time)}
                    </span>
                  </Card.Header>
                  <Card.Body>
                    <Card.Text>
                      
                      <span>{tiebreaker.question}</span>
                    </Card.Text>
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
          <h6>User Picks:</h6>
          <ListGroup>
            {selectedGame?.picks ? (
              (() => {
                const totalPicks = selectedGame.picks.length;
                const homePicks = selectedGame.picks.filter(pick => pick.picked_team === selectedGame.home_team).length;
                const awayPicks = selectedGame.picks.filter(pick => pick.picked_team === selectedGame.away_team).length;
                const homePercentage = totalPicks > 0 ? ((homePicks / totalPicks) * 100).toFixed(0) : 0;
                const awayPercentage = totalPicks > 0 ? ((awayPicks / totalPicks) * 100).toFixed(0) : 0;

                return (
                  <>
                    <ListGroup.Item 
                      action 
                      onClick={() => setShowAwayPicks(!showAwayPicks)} 
                      className="d-flex justify-content-between align-items-center"
                    >
                      <strong>{selectedGame.away_team} +{selectedGame.spread}</strong>{awayPicks} picked ({awayPercentage}%)
                    </ListGroup.Item>
                    {showAwayPicks && (
                      <div className="d-flex flex-wrap justify-content-center transition-dropdown">
                        {selectedGame.picks.filter(pick => pick.picked_team === selectedGame.away_team).map((pick, index) => (
                          <Badge key={index} bg="secondary" className="m-1">
                            {pick.full_name}
                          </Badge>
                        ))}
                      </div>
                    )}
                    <br></br>
                    <ListGroup.Item 
                      action 
                      onClick={() => setShowHomePicks(!showHomePicks)} 
                      className="d-flex justify-content-between align-items-center"
                    >
                      <strong>{selectedGame.home_team} -{selectedGame.spread}</strong>{homePicks} picked ({homePercentage}%)
                    </ListGroup.Item>
                    {showHomePicks && (
                      <div className="d-flex flex-wrap justify-content-center transition-dropdown">
                        {selectedGame.picks.filter(pick => pick.picked_team === selectedGame.home_team).map((pick, index) => (
                          <Badge key={index} bg="secondary" className="m-1">
                            {pick.full_name}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </>
                );
              })()
            ) : (
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
            {selectedTiebreaker?.picks && selectedTiebreaker.picks
              .sort((a, b) => {
                // Sort by answer text alphabetically
                const answerA = isNaN(a.answer) ? a.answer : (Number.isInteger(a.answer) ? a.answer : Math.floor(a.answer)).toString();
                const answerB = isNaN(b.answer) ? b.answer : (Number.isInteger(b.answer) ? b.answer : Math.floor(b.answer)).toString();
                return answerA.localeCompare(answerB);
              })
              .map((pick, index) => (
                <ListGroup.Item 
                  key={index}
                  className="d-flex justify-content-between align-items-center p-2"
                >
                  <span className="text-truncate">{pick.full_name}</span>
                  <Badge bg="secondary" className="p-2">
                    {isNaN(pick.answer) ? pick.answer : (Number.isInteger(pick.answer) ? pick.answer : Math.floor(pick.answer))}
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