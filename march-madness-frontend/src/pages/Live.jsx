import { useEffect, useState } from "react";
import axios from "axios";
import { Alert, Card, ListGroup, Badge, Container, Spinner, Modal, Button, Row, Col, Pagination, Form } from "react-bootstrap";
import { API_URL } from "../config";

export default function Live() {
  const [liveGames, setLiveGames] = useState([]);
  const [liveTiebreakers, setLiveTiebreakers] = useState([]);
  const [gameScores, setGameScores] = useState([]); // New state for game scores
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedGame, setSelectedGame] = useState(null);
  const [selectedTiebreaker, setSelectedTiebreaker] = useState(null);
  const [showGameModal, setShowGameModal] = useState(false);
  const [showTiebreakerModal, setShowTiebreakerModal] = useState(false);
  const [showAwayPicks, setShowAwayPicks] = useState(false);
  const [showHomePicks, setShowHomePicks] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortOption, setSortOption] = useState("answer"); // "answer" or "name"
  const picksPerPage = 12; // Show more picks per page

  useEffect(() => {
    fetchLiveData();
    fetchGameScores(); // Fetch game scores on component mount
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

  const fetchGameScores = () => {
    axios.get(`${API_URL}/api/gamescores`)
      .then(response => {
        setGameScores(response.data); // Set the game scores
      })
      .catch(err => {
        console.error(err);
        setError('Failed to load game scores. Please try again.');
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
    setCurrentPage(1);
    setSearchTerm("");
  };

  const handleCloseGameModal = () => {
    setShowGameModal(false);
    setSelectedGame(null);
  };

  const handleCloseTiebreakerModal = () => {
    setShowTiebreakerModal(false);
    setSelectedTiebreaker(null);
  };

  // Function to get the score for the selected game
  const getGameScore = (game) => {
    return gameScores.find(score => 
      (score.AwayTeam === game.away_team && score.HomeTeam === game.home_team) ||
      (score.AwayTeam === game.home_team && score.HomeTeam === game.away_team) ||
      (score.AwayTeam.includes(game.away_team) || score.AwayTeam.includes(game.home_team)) ||
      (score.HomeTeam.includes(game.away_team) || score.HomeTeam.includes(game.home_team))
    );
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
              <div key={game.game_id} className="col-md-6 col-lg-4 mb-4">
                <Card 
                  onClick={() => handleGameClick(game)}
                  style={{ cursor: 'pointer' }}
                  className="hover-shadow h-100"
                >
                  <Card.Header className="d-flex justify-content-between align-items-center">
                    <Badge bg="info" className="py-2 px-3" style={{ fontSize: '1rem' }}>
                      {(() => {
                        const score = getGameScore(game);
                        return score ? score.Time : 'Time not available';
                      })()}
                    </Badge>
                    <Badge bg="primary" className="py-2 px-3" style={{ fontSize: '1rem' }}>
                      {game.spread > 0 
                        ? `${game.home_team} -${game.spread}` 
                        : `${game.away_team} -${-game.spread}`}
                    </Badge>
                  </Card.Header>
                  <Card.Body className="text-center">
                    <Card.Text style={{ fontSize: '1.25rem' }}>
                      {(() => {
                        const score = getGameScore(game);
                        return score 
                          ? (
                            <>
                              <span className="fw-bold text-truncate d-inline-block" style={{ maxWidth: '35%', verticalAlign: 'middle' }}>{score.AwayTeam}</span>
                              <span className="mx-1 fs-4 d-inline-block" style={{ verticalAlign: 'middle' }}>{score.AwayScore}</span>
                              <span className="mx-1 d-inline-block" style={{ verticalAlign: 'middle' }}>@</span>
                              <span className="mx-1 fs-4 d-inline-block" style={{ verticalAlign: 'middle' }}>{score.HomeScore}</span>
                              <span className="fw-bold text-truncate d-inline-block" style={{ maxWidth: '35%', verticalAlign: 'middle' }}>{score.HomeTeam}</span>
                            </>
                          )
                          : (
                            <>
                              <span className="text-truncate d-inline-block" style={{ maxWidth: '40%', verticalAlign: 'middle' }}>{game.away_team}</span>
                              <span className="mx-2 d-inline-block" style={{ verticalAlign: 'middle' }}>@</span>
                              <span className="text-truncate d-inline-block" style={{ maxWidth: '40%', verticalAlign: 'middle' }}>{game.home_team}</span>
                            </>
                          ); // Fallback if score is not available
                      })()}
                    </Card.Text>
                  </Card.Body>
                </Card>
              </div>
            ))}
            
            {/* Include tiebreakers in the same row as games */}
            {liveTiebreakers.map((tiebreaker) => (
              <div key={tiebreaker.tiebreaker_id} className="col-md-6 col-lg-4 mb-4">
                <Card 
                  onClick={() => handleTiebreakerClick(tiebreaker)}
                  style={{ cursor: 'pointer' }}
                  className="hover-shadow h-100"
                >
                  <Card.Header className="d-flex justify-content-between align-items-center">
                    <Badge bg="info" className="py-2 px-3" style={{ fontSize: '1rem' }}>
                      {tiebreaker.question.includes("Lock") ? "Lock" : "Tiebreaker"}
                    </Badge>
                    <Badge bg="primary" className="py-2 px-3" style={{ fontSize: '1rem' }}>
                      {formatGameDate(tiebreaker.start_time)}
                    </Badge>
                  </Card.Header>
                  <Card.Body className="text-center">
                    <Card.Text style={{ fontSize: '1.1rem' }}>
                      {tiebreaker.question}
                    </Card.Text>
                  </Card.Body>
                </Card>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Game Picks Modal */}
      <Modal show={showGameModal} onHide={handleCloseGameModal} size="lg">
        <Modal.Header closeButton className="bg-light">
          <Modal.Title className="w-100 text-center">
            {selectedGame && (
              <div className="d-flex justify-content-between align-items-center">
                {/* Centered Team Names */}
                <div className="text-center w-100">
                  <span className="mx-3">{selectedGame.away_team} @ {selectedGame.home_team}</span>
                </div>
              </div>
            )}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body className="py-4">
          {selectedGame && (
            <>
              {(() => {
                const score = getGameScore(selectedGame);
                return (
                  <div className="text-center mb-4">
                    {/* Centered Time Badge */}
                    <Badge bg="info" className="py-2 px-3" style={{ fontSize: '1rem' }}>
                      {score ? score.Time : "Time not available"}
                    </Badge>
                    <div className="d-flex justify-content-center align-items-center" style={{ fontSize: '1.5rem' }}>
                      <span className="fw-bold text-truncate" style={{ maxWidth: '30%' }}>{score.AwayTeam}</span>
                      <span className="mx-2 fs-2">{score.AwayScore}</span>
                      <span className="mx-2">@</span>
                      <span className="mx-2 fs-2">{score.HomeScore}</span>
                      <span className="fw-bold text-truncate" style={{ maxWidth: '30%' }}>{score.HomeTeam}</span>
                    </div>
                  </div>
                );
              })()}
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
                          className="d-flex justify-content-between align-items-center py-3"
                        >
                          <strong className="text-secondary">{selectedGame.away_team} {selectedGame.spread}</strong>
                          <Badge bg="secondary" className="py-2 px-3">
                            {awayPicks} picked ({awayPercentage}%)
                          </Badge>
                        </ListGroup.Item>
                        {showAwayPicks && (
                          <div className="d-flex flex-wrap justify-content-center p-3 bg-light">
                            {selectedGame.picks.filter(pick => pick.picked_team === selectedGame.away_team).map((pick, index) => (
                              <Badge key={index} bg="secondary" className="m-1 py-2 px-3">
                                {pick.full_name}
                              </Badge>
                            ))}
                          </div>
                        )}
                        <ListGroup.Item 
                          action 
                          onClick={() => setShowHomePicks(!showHomePicks)} 
                          className="d-flex justify-content-between align-items-center py-3"
                        >
                          <strong className="text-secondary">{selectedGame.home_team} {-1 * selectedGame.spread}</strong>
                          <Badge bg="secondary" className="py-2 px-3">
                            {homePicks} picked ({homePercentage}%)
                          </Badge>
                        </ListGroup.Item>
                        {showHomePicks && (
                          <div className="d-flex flex-wrap justify-content-center p-3 bg-light">
                            {selectedGame.picks.filter(pick => pick.picked_team === selectedGame.home_team).map((pick, index) => (
                              <Badge key={index} bg="secondary" className="m-1 py-2 px-3">
                                {pick.full_name}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </>
                    );
                  })()
                ) : (
                  <ListGroup.Item className="text-center text-muted py-3">No picks for this game yet</ListGroup.Item>
                )}
              </ListGroup>
            </>
          )}
        </Modal.Body>
        <Modal.Footer className="bg-light">
          <Button variant="secondary" onClick={handleCloseGameModal}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Tiebreaker Modal */}
      <Modal show={showTiebreakerModal} onHide={handleCloseTiebreakerModal} size="lg">
        <Modal.Header closeButton className="bg-light">
          <Modal.Title className="w-100 text-center">
            {selectedTiebreaker && (
              <div className="d-flex justify-content-between align-items-center">
                <Badge bg="info" className="py-2 px-3" style={{ fontSize: '1rem' }}>
                  {selectedTiebreaker.question.includes("Lock") ? "Lock" : "Tiebreaker"}
                </Badge>
                <span className="mx-3 text-truncate" style={{ maxWidth: '50%' }}>{selectedTiebreaker && selectedTiebreaker.question}</span>
                <Badge bg="primary" className="py-2 px-3" style={{ fontSize: '1rem' }}>
                  {selectedTiebreaker && formatGameDate(selectedTiebreaker.start_time).split(',')[0]}
                </Badge>
              </div>
            )}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body className="py-4">
          {selectedTiebreaker && (
            <>
              {selectedTiebreaker?.picks && selectedTiebreaker.picks.length > 0 ? (
                <>
                  <div className="mb-4">
                    <Row className="align-items-center">
                      <Col md={5}>
                        <Form.Control
                          type="text"
                          placeholder="Search by name..."
                          value={searchTerm}
                          onChange={(e) => {
                            setSearchTerm(e.target.value);
                            setCurrentPage(1);
                          }}
                          className="mb-2 mb-md-0"
                        />
                      </Col>
                      <Col md={4}>
                        <Form.Select 
                          value={sortOption}
                          onChange={(e) => {
                            setSortOption(e.target.value);
                            setCurrentPage(1);
                          }}
                        >
                          <option value="answer">Sort by Answer</option>
                          <option value="name">Sort by Name</option>
                        </Form.Select>
                      </Col>
                      <Col md={3} className="text-end">
                        <Badge bg="primary" className="py-2 px-3">
                          {selectedTiebreaker.picks.length} responses
                        </Badge>
                      </Col>
                    </Row>
                  </div>
                  
                  <Row>
                    {(() => {
                      // Filter picks based on search term
                      const filteredPicks = selectedTiebreaker.picks
                        .filter(pick => 
                          pick.full_name.toLowerCase().includes(searchTerm.toLowerCase())
                        );
                      
                      // Sort picks based on option
                      const sortedPicks = [...filteredPicks].sort((a, b) => {
                        if (sortOption === "name") {
                          return a.full_name.localeCompare(b.full_name);
                        } else {
                          // Sort by answer
                          const answerA = isNaN(a.answer) ? a.answer : (Number.isInteger(a.answer) ? a.answer : Math.floor(a.answer)).toString();
                          const answerB = isNaN(b.answer) ? b.answer : (Number.isInteger(b.answer) ? b.answer : Math.floor(b.answer)).toString();
                          return answerA.localeCompare(answerB);
                        }
                      });
                      
                      // Paginate picks
                      const indexOfLastPick = currentPage * picksPerPage;
                      const indexOfFirstPick = indexOfLastPick - picksPerPage;
                      const currentPicks = sortedPicks.slice(indexOfFirstPick, indexOfLastPick);
                      
                      // Calculate total pages
                      const totalPages = Math.ceil(sortedPicks.length / picksPerPage);
                      
                      return (
                        <>
                          {currentPicks.map((pick, index) => (
                            <Col key={index} xs={12} sm={6} md={4} className="mb-3">
                              <div className="border rounded p-2 h-100 d-flex flex-column justify-content-between">
                                <div className="text-truncate fw-bold text-secondary mb-1" title={pick.full_name}>
                                  {pick.full_name}
                                </div>
                                <Badge bg="secondary" className="py-2 px-3 align-self-end">
                                  {isNaN(pick.answer) ? pick.answer : (Number.isInteger(pick.answer) ? pick.answer : Math.floor(pick.answer))}
                                </Badge>
                              </div>
                            </Col>
                          ))}
                          
                          {sortedPicks.length > picksPerPage && (
                            <Col xs={12} className="mt-3 d-flex justify-content-center">
                              <Pagination>
                                <Pagination.First 
                                  onClick={() => setCurrentPage(1)} 
                                  disabled={currentPage === 1}
                                />
                                <Pagination.Prev 
                                  onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                                  disabled={currentPage === 1}
                                />
                                
                                {Array.from({ length: Math.min(5, totalPages) }).map((_, idx) => {
                                  // Show pagination centered around current page
                                  let pageNum;
                                  if (totalPages <= 5) {
                                    pageNum = idx + 1;
                                  } else if (currentPage <= 3) {
                                    pageNum = idx + 1;
                                  } else if (currentPage >= totalPages - 2) {
                                    pageNum = totalPages - 4 + idx;
                                  } else {
                                    pageNum = currentPage - 2 + idx;
                                  }
                                  
                                  return (
                                    <Pagination.Item
                                      key={pageNum}
                                      active={pageNum === currentPage}
                                      onClick={() => setCurrentPage(pageNum)}
                                    >
                                      {pageNum}
                                    </Pagination.Item>
                                  );
                                })}
                                
                                <Pagination.Next 
                                  onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                                  disabled={currentPage === totalPages}
                                />
                                <Pagination.Last 
                                  onClick={() => setCurrentPage(totalPages)}
                                  disabled={currentPage === totalPages}
                                />
                              </Pagination>
                            </Col>
                          )}
                          
                          {currentPicks.length === 0 && (
                            <Col xs={12} className="text-center py-4">
                              <p className="text-muted">No results match your search.</p>
                            </Col>
                          )}
                        </>
                      );
                    })()}
                  </Row>
                </>
              ) : (
                <div className="text-center text-muted py-4">
                  <p>No answers submitted yet</p>
                </div>
              )}
            </>
          )}
        </Modal.Body>
        <Modal.Footer className="bg-light">
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