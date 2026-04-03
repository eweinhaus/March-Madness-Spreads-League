import { useEffect, useState, useMemo, useCallback } from "react";
import { Alert, Card, ListGroup, Badge, Container, Spinner, Modal, Button, Row, Col, Pagination, Form } from "react-bootstrap";
import { FaLock } from "react-icons/fa";
import { useNavigate } from "react-router-dom";
import api from "../api";

export default function Live() {
  const [liveGames, setLiveGames] = useState([]);
  const [liveTiebreakers, setLiveTiebreakers] = useState([]);
  const [gameScores, setGameScores] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [backgroundRefreshing, setBackgroundRefreshing] = useState(false);
  const [selectedGame, setSelectedGame] = useState(null);
  const [selectedTiebreaker, setSelectedTiebreaker] = useState(null);
  const [showGameModal, setShowGameModal] = useState(false);
  const [showTiebreakerModal, setShowTiebreakerModal] = useState(false);
  const [showAwayPicks, setShowAwayPicks] = useState(false);
  const [showHomePicks, setShowHomePicks] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortOption, setSortOption] = useState("answer");
  const [gamePicks, setGamePicks] = useState({});
  const [tiebreakerPicks, setTiebreakerPicks] = useState({});
  const [loadingPicks, setLoadingPicks] = useState(false);
  const picksPerPage = 12;
  const navigate = useNavigate();

  useEffect(() => {
    fetchLiveData();
    fetchGameScores();
    
    const interval = setInterval(() => {
      setBackgroundRefreshing(true);
      fetchLiveDataBackground();
      fetchGameScoresBackground();
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);

  const handleAuthError = useCallback((err) => {
    if (err.response?.status === 401) {
      navigate('/login');
      return true;
    }
    return false;
  }, [navigate]);

  const fetchLiveData = () => {
    setLoading(true);
    setError(null);
    api.get('/live')
      .then((res) => {
        const data = res.data || {};
        setLiveGames(Array.isArray(data.live_games) ? data.live_games : []);
        setLiveTiebreakers(Array.isArray(data.live_tiebreakers) ? data.live_tiebreakers : []);
        setError(null);
      })
      .catch(err => {
        if (!handleAuthError(err)) {
          console.error(err);
          setError('Failed to load live data. Please try again.');
        }
      })
      .finally(() => {
        setLoading(false);
      });
  };

  const fetchLiveDataBackground = () => {
    api.get('/live')
      .then((res) => {
        const data = res.data || {};
        setLiveGames(Array.isArray(data.live_games) ? data.live_games : []);
        setLiveTiebreakers(Array.isArray(data.live_tiebreakers) ? data.live_tiebreakers : []);
        setError(null);
      })
      .catch(err => {
        if (!handleAuthError(err)) {
          console.error('Background refresh error:', err);
        }
      })
      .finally(() => {
        setBackgroundRefreshing(false);
      });
  };

  const fetchGameScores = () => {
    api.get('/api/gamescores')
      .then(response => {
        setGameScores(response.data);
      })
      .catch(err => {
        if (!handleAuthError(err)) {
          console.error(err);
          setError('Failed to load game scores. Please try again.');
        }
      });
  };

  const fetchGameScoresBackground = () => {
    api.get('/api/gamescores')
      .then(response => {
        setGameScores(response.data);
      })
      .catch(err => {
        if (!handleAuthError(err)) {
          console.error('Background game scores error:', err);
        }
      });
  };

  const fetchGamePicks = useCallback(async (gameId) => {
    if (gamePicks[gameId]) return gamePicks[gameId];
    
    setLoadingPicks(true);
    
    try {
      const response = await api.get(`/live_games/${gameId}/picks`);
      const picks = response.data;
      setGamePicks(prev => ({ ...prev, [gameId]: picks }));
      return picks;
    } catch (err) {
      if (!handleAuthError(err)) {
        console.error(err);
        setError('Failed to load game picks. Please try again.');
      }
      return [];
    } finally {
      setLoadingPicks(false);
    }
  }, [gamePicks, handleAuthError]);

  const fetchTiebreakerPicks = useCallback(async (tiebreakerId) => {
    if (tiebreakerPicks[tiebreakerId]) return tiebreakerPicks[tiebreakerId];
    
    setLoadingPicks(true);
    
    try {
      const response = await api.get(`/live_tiebreakers/${tiebreakerId}/picks`);
      const picks = response.data;
      setTiebreakerPicks(prev => ({ ...prev, [tiebreakerId]: picks }));
      return picks;
    } catch (err) {
      if (!handleAuthError(err)) {
        console.error(err);
        setError('Failed to load tiebreaker picks. Please try again.');
      }
      return [];
    } finally {
      setLoadingPicks(false);
    }
  }, [tiebreakerPicks, handleAuthError]);

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

  const handleGameClick = async (game) => {
    setSelectedGame(game);
    setShowGameModal(true);
    if (!gamePicks[game.game_id]) {
      await fetchGamePicks(game.game_id);
    }
  };

  const handleTiebreakerClick = async (tiebreaker) => {
    setSelectedTiebreaker(tiebreaker);
    setShowTiebreakerModal(true);
    setCurrentPage(1);
    setSearchTerm("");
    if (!tiebreakerPicks[tiebreaker.tiebreaker_id]) {
      await fetchTiebreakerPicks(tiebreaker.tiebreaker_id);
    }
  };

  const handleCloseGameModal = () => {
    setShowGameModal(false);
    setSelectedGame(null);
  };

  const handleCloseTiebreakerModal = () => {
    setShowTiebreakerModal(false);
    setSelectedTiebreaker(null);
  };

  const normalizeTeamName = useCallback((teamName) => {
    if (!teamName) return '';
    
    let normalized = teamName
      .replace(/\b(Crimson Tide|Commodores|Bulldogs|Tigers|Wildcats|Eagles|Bears|Cowboys|Trojans|Spartans|Volunteers|Aggies|Longhorns|Sooners|Buckeyes|Wolverines|Fighting Irish|Golden Bears|Blue Devils|Tar Heels|Seminoles|Hurricanes|Hokies|Cavaliers|Demon Deacons|Yellow Jackets|Orange|Cardinals|Panthers|Huskies|Cougars|Sun Devils|Ducks|Beavers|Utes|Buffaloes|Buffs|Bruins|Mountaineers|Jayhawks|Cyclones|Red Raiders|Horned Frogs|Mountaineers|Cornhuskers|Badgers|Gophers|Hawkeyes|Illini|Hoosiers|Terrapins|Nittany Lions|Scarlet Knights|Boilermakers)\b/gi, '')
      .replace(/^St\.\s+/g, 'Saint ')
      .replace(/\bSt\.\b/g, 'State')
      .replace(/\bW\.\b/g, 'Western')
      .replace(/\bC\.\b/g, 'Central')
      .replace(/\bE\.\b/g, 'Eastern')
      .replace(/\bSo\.\b/g, 'Southern')
      .replace(/\bN\.\b/g, 'Northern')
      .replace(/\bTenn\b/g, 'Tennessee')
      .replace(/\bFla\.\b/g, 'Florida')
      .replace(/\bArk\b/g, 'Arkansas')
      .replace(/\bSE\b/g, 'Southeast')
      .replace(/\bVandy\b/gi, 'Vanderbilt')
      .replace(/\bBama\b/gi, 'Alabama')
      .replace(/\bMiami \(FL\)/gi, 'Miami')
      .replace(/\bMiami-FL\b/gi, 'Miami')
      .replace(/\bState\b/g, 'State')
      .replace(/\bWestern\b/g, 'Western')
      .replace(/\bCentral\b/g, 'Central')
      .replace(/\bEastern\b/g, 'Eastern')
      .replace(/\bSouthern\b/g, 'Southern')
      .replace(/\bNorthern\b/g, 'Northern')
      .replace(/\bTennessee\b/g, 'Tennessee')
      .replace(/\bFlorida\b/g, 'Florida')
      .replace(/\bArkansas\b/g, 'Arkansas')
      .replace(/\bSoutheast\b/g, 'Southeast')
      .toLowerCase()
      .trim();
    
    normalized = normalized.replace(/\s+/g, ' ').trim();
    
    if (normalized === '') {
      return teamName.toLowerCase().trim();
    }
    
    return normalized;
  }, []);

  const teamNamesMatch = useCallback((name1, name2) => {
    if (!name1 || !name2) return false;
    
    const normalized1 = normalizeTeamName(name1);
    const normalized2 = normalizeTeamName(name2);
    
    if (normalized1 === normalized2) return true;
    
    return normalized1.includes(normalized2) || normalized2.includes(normalized1);
  }, [normalizeTeamName]);

  const getGameScore = useCallback((game) => {
    return gameScores.find(score => {
      if ((score.AwayTeam === game.away_team && score.HomeTeam === game.home_team) ||
          (score.AwayTeam === game.home_team && score.HomeTeam === game.away_team)) {
        return true;
      }
      
      const scoreAwayNorm = score.AwayTeamNormalized || normalizeTeamName(score.AwayTeam);
      const scoreHomeNorm = score.HomeTeamNormalized || normalizeTeamName(score.HomeTeam);
      const gameAwayNorm = normalizeTeamName(game.away_team);
      const gameHomeNorm = normalizeTeamName(game.home_team);
      
      if ((scoreAwayNorm === gameAwayNorm && scoreHomeNorm === gameHomeNorm) ||
          (scoreAwayNorm === gameHomeNorm && scoreHomeNorm === gameAwayNorm)) {
        return true;
      }
      
      if (teamNamesMatch(score.AwayTeam, game.away_team) && teamNamesMatch(score.HomeTeam, game.home_team)) {
        return true;
      }
      
      if (teamNamesMatch(score.AwayTeam, game.home_team) && teamNamesMatch(score.HomeTeam, game.away_team)) {
        return true;
      }
      
      return false;
    });
  }, [gameScores, teamNamesMatch, normalizeTeamName]);

  const selectedGamePicks = useMemo(() => {
    if (!selectedGame || !gamePicks[selectedGame.game_id]) return null;
    return gamePicks[selectedGame.game_id];
  }, [selectedGame, gamePicks]);

  const selectedTiebreakerPicks = useMemo(() => {
    if (!selectedTiebreaker || !tiebreakerPicks[selectedTiebreaker.tiebreaker_id]) return null;
    return tiebreakerPicks[selectedTiebreaker.tiebreaker_id];
  }, [selectedTiebreaker, tiebreakerPicks]);

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
          <div className="d-flex justify-content-between align-items-center mb-4">
            <h2>Live Contests</h2>
            {backgroundRefreshing && (
              <small className="text-muted">
                <i className="bi bi-arrow-clockwise me-1"></i>
                Updating...
              </small>
            )}
          </div>
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
                  className={`hover-shadow h-100 ${backgroundRefreshing ? 'opacity-75' : ''}`}
                >
                  <Card.Header className="d-flex justify-content-between align-items-center">
                    <Badge bg="info" className="py-2 px-3" style={{ fontSize: '1rem' }}>
                      {(() => {
                        const score = getGameScore(game);
                        return score ? score.Time : 'Starting soon';
                      })()}
                    </Badge>
                    <Badge bg="primary" className="py-2 px-3" style={{ fontSize: '1rem' }}>
                      {game.spread > 0 
                        ? `${game.home_team} -${game.spread}` 
                        : `${game.away_team} -${-game.spread}`}
                    </Badge>
                  </Card.Header>
                  <Card.Body className="text-center">
                    <Card.Text style={{ fontSize: '1rem' }}>
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
                          );
                      })()}
                    </Card.Text>
                    <div className="mt-2">
                      <small className="text-muted">
                        {game.total_picks || 0} picks • {game.home_picks || 0} home • {game.away_picks || 0} away
                      </small>
                    </div>
                  </Card.Body>
                </Card>
              </div>
            ))}
            
            {liveTiebreakers.map((tiebreaker) => (
              <div key={tiebreaker.tiebreaker_id} className="col-md-6 col-lg-4 mb-4">
                <Card 
                  onClick={() => handleTiebreakerClick(tiebreaker)}
                  style={{ cursor: 'pointer' }}
                  className={`hover-shadow h-100 ${backgroundRefreshing ? 'opacity-75' : ''}`}
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
                    <div className="mt-2">
                      <small className="text-muted">
                        {tiebreaker.total_picks || 0} responses
                      </small>
                    </div>
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
                    <Badge bg="info" className="py-2 px-3" style={{ fontSize: '1rem' }}>
                      {score ? score.Time : "Starting soon"}
                    </Badge>
                    {score ? (
                      <div className="d-flex justify-content-center align-items-center" style={{ fontSize: '1.25rem' }}>
                        <span className="fw-bold text-truncate" style={{ maxWidth: '30%' }}>{score.AwayTeam}</span>
                        <span className="mx-2 fs-4">{score.AwayScore}</span>
                        <span className="mx-2">@</span>
                        <span className="mx-2 fs-4">{score.HomeScore}</span>
                        <span className="fw-bold text-truncate" style={{ maxWidth: '30%' }}>{score.HomeTeam}</span>
                      </div>
                    ) : (
                      <div className="d-flex justify-content-center align-items-center" style={{ fontSize: '1.25rem' }}>
                        <span className="fw-bold text-truncate" style={{ maxWidth: '30%' }}>{selectedGame.away_team}</span>
                        <span className="mx-2">@</span>
                        <span className="fw-bold text-truncate" style={{ maxWidth: '30%' }}>{selectedGame.home_team}</span>
                      </div>
                    )}
                  </div>
                );
              })()}
              
              {loadingPicks ? (
                <div className="text-center py-4">
                  <Spinner animation="border" size="sm" />
                  <p className="mt-2">Loading picks...</p>
                </div>
              ) : selectedGamePicks ? (
                <ListGroup>
                  {(() => {
                    const totalPicks = selectedGamePicks.length;
                    const homePicks = selectedGamePicks.filter(pick => pick.picked_team === selectedGame.home_team).length;
                    const awayPicks = selectedGamePicks.filter(pick => pick.picked_team === selectedGame.away_team).length;
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
                            {selectedGamePicks.filter(pick => pick.picked_team === selectedGame.away_team).map((pick, index) => (
                              <Badge 
                                key={index} 
                                bg="secondary" 
                                className="m-1 py-2 px-3 d-flex align-items-center gap-2" 
                                style={{
                                  ...(pick.lock && { 
                                    border: '3px solid #ffc107', 
                                    borderRadius: '6px',
                                    position: 'relative'
                                  })
                                }}
                              >
                                {pick.display_name}
                                {pick.lock && (
                                  <FaLock className="text-dark" size={12} title="Lock of the day" />
                                )}
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
                            {selectedGamePicks.filter(pick => pick.picked_team === selectedGame.home_team).map((pick, index) => (
                              <Badge 
                                key={index} 
                                bg="secondary" 
                                className="m-1 py-2 px-3 d-flex align-items-center gap-2" 
                                style={{
                                  ...(pick.lock && { 
                                    border: '3px solid #ffc107', 
                                    borderRadius: '6px',
                                    position: 'relative'
                                  })
                                }}
                              >
                                {pick.display_name}
                                {pick.lock && (
                                  <FaLock className="text-dark" size={12} title="Lock of the day" />
                                )}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </>
                    );
                  })()}
                </ListGroup>
              ) : (
                <ListGroup.Item className="text-center text-muted py-3">No picks for this game yet</ListGroup.Item>
              )}
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
              {loadingPicks ? (
                <div className="text-center py-4">
                  <Spinner animation="border" size="sm" />
                  <p className="mt-2">Loading responses...</p>
                </div>
              ) : selectedTiebreakerPicks && selectedTiebreakerPicks.length > 0 ? (
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
                          {selectedTiebreakerPicks.length} responses
                        </Badge>
                      </Col>
                    </Row>
                  </div>
                  
                  <Row>
                    {(() => {
                      const filteredPicks = selectedTiebreakerPicks
                        .filter(pick => 
                          pick.display_name.toLowerCase().includes(searchTerm.toLowerCase())
                        );
                      
                      const sortedPicks = [...filteredPicks].sort((a, b) => {
                        if (sortOption === "name") {
                          return a.display_name.localeCompare(b.display_name);
                        } else {
                          const answerA = isNaN(a.answer) ? a.answer : (Number.isInteger(a.answer) ? a.answer : Math.floor(a.answer)).toString();
                          const answerB = isNaN(b.answer) ? b.answer : (Number.isInteger(b.answer) ? b.answer : Math.floor(b.answer)).toString();
                          return answerA.localeCompare(answerB);
                        }
                      });
                      
                      const indexOfLastPick = currentPage * picksPerPage;
                      const indexOfFirstPick = indexOfLastPick - picksPerPage;
                      const currentPicks = sortedPicks.slice(indexOfFirstPick, indexOfLastPick);
                      
                      const totalPages = Math.ceil(sortedPicks.length / picksPerPage);
                      
                      return (
                        <>
                          {currentPicks.map((pick, index) => (
                            <Col key={index} xs={12} sm={6} md={4} className="mb-3">
                              <div className="border rounded p-2 h-100 d-flex flex-column justify-content-between">
                                <div className="text-truncate fw-bold text-secondary mb-1" title={pick.display_name}>
                                  {pick.display_name}
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
