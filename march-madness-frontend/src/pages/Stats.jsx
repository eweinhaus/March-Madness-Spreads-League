import { useEffect, useState } from "react";
import axios from "axios";
import { Card, Row, Col, Alert, Badge, ProgressBar, Modal, Table } from "react-bootstrap";
import { FaLock, FaTrophy, FaFire, FaHeart, FaStar, FaArrowUp, FaArrowDown, FaChartLine } from "react-icons/fa";
import { API_URL } from "../config";

export default function Stats() {
  const [stats, setStats] = useState([]);
  const [error, setError] = useState(null);
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [playerDetails, setPlayerDetails] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = () => {
    axios.get(`${API_URL}/stats`)
      .then(res => {
        setStats(res.data);
        setError(null);
      })
      .catch(err => {
        console.error('Failed to load stats:', err);
        setError('Failed to load player statistics. Please try again.');
      });
  };

  const handlePlayerClick = async (player) => {
    setSelectedPlayer(player);
    setShowModal(true);
    setLoadingDetails(true);

    try {
      console.log('Fetching detailed stats for:', player.username);
      const encodedUsername = encodeURIComponent(player.username);
      const response = await axios.get(`${API_URL}/stats/${encodedUsername}`);
      console.log('Detailed stats response:', response.data);
      setPlayerDetails(response.data);
    } catch (err) {
      console.error('Failed to load player details:', err);
      console.error('Error response:', err.response?.data);
      console.error('Error status:', err.response?.status);
      setPlayerDetails(null); // This will trigger the error alert
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setSelectedPlayer(null);
    setPlayerDetails(null);
  };

  const formatPercentage = (value) => {
    return value ? `${value}%` : '0%';
  };

  const getWinRateColor = (percentage) => {
    if (percentage >= 70) return 'success';
    if (percentage >= 60) return 'info';
    if (percentage >= 50) return 'warning';
    return 'danger';
  };

  const getLockRateColor = (percentage) => {
    if (percentage >= 80) return 'success';
    if (percentage >= 60) return 'info';
    if (percentage >= 40) return 'warning';
    return 'danger';
  };

  return (
    <div className="container my-3 my-md-5 px-2 px-md-3">
      <div className="d-flex align-items-center mb-4">
        <h2 className="mb-0">Player Statistics</h2>
      </div>

      {error && (
        <Alert variant="danger" className="mb-4">
          {error}
        </Alert>
      )}

      {stats.length === 0 && !error ? (
        <Alert variant="info">
          Loading player statistics...
        </Alert>
      ) : (
        <Row>
          {stats.map((player, index) => (
            <Col key={player.username} lg={4} xl={3} className="mb-4">
              <Card
                className="h-100 shadow-sm"
                style={{ cursor: 'pointer' }}
                onClick={() => handlePlayerClick(player)}
              >
                <Card.Header className="bg-primary text-white py-3">
                  <div className="d-flex justify-content-between align-items-center">
                    <h5 className="mb-0" style={{ fontSize: '1.25rem' }}>{player.full_name}</h5>
                    <Badge bg="light" text="dark" className="fs-6">
                      #{index + 1}
                    </Badge>
                  </div>
                </Card.Header>

                <Card.Body className="pb-2">
                  {/* Overall Record Section */}
                  <div className="mb-4">
                    <h6 className="d-flex align-items-center mb-3">
                      <FaTrophy className="me-2 text-warning" />
                      Overall Record
                    </h6>

                    <div className="mb-2">
                      <div className="d-flex justify-content-between mb-1">
                        <small className="text-muted">Total Picks</small>
                        <strong>{player.total_picks}</strong>
                      </div>
                      <ProgressBar className="mb-2">
                        <ProgressBar
                          variant="success"
                          now={(player.correct_picks / Math.max(player.total_picks, 1)) * 100}
                          label={`${player.correct_picks}W`}
                        />
                        <ProgressBar
                          variant="danger"
                          now={(player.incorrect_picks / Math.max(player.total_picks, 1)) * 100}
                          label={`${player.incorrect_picks}L`}
                        />
                        <ProgressBar
                          variant="warning"
                          now={(player.push_games / Math.max(player.total_picks, 1)) * 100}
                          label={`${player.push_games}P`}
                        />
                      </ProgressBar>
                    </div>

                    <div className="d-flex justify-content-between align-items-center">
                      <span className="small text-muted">Win Rate</span>
                      <Badge bg={getWinRateColor(player.win_percentage)} className="fs-6">
                        {formatPercentage(player.win_percentage)}
                      </Badge>
                    </div>
                  </div>

                  {/* Lock Record Section */}
                  <div className="mb-4">
                    <h6 className="d-flex align-items-center mb-3">
                      <FaLock className="me-2 text-danger" />
                      Lock Record
                    </h6>

                    <div className="mb-2">
                      <div className="d-flex justify-content-between mb-1">
                        <small className="text-muted">Total Locks</small>
                        <strong>{player.total_locks}</strong>
                      </div>
                      {player.total_locks > 0 && (
                        <ProgressBar className="mb-2">
                          <ProgressBar
                            variant="success"
                            now={(player.correct_locks / player.total_locks) * 100}
                            label={`${player.correct_locks}W`}
                          />
                          <ProgressBar
                            variant="danger"
                            now={(player.incorrect_locks / player.total_locks) * 100}
                            label={`${player.incorrect_locks}L`}
                          />
                        </ProgressBar>
                      )}
                    </div>

                    <div className="d-flex justify-content-between align-items-center">
                      <span className="small text-muted">Lock Success Rate</span>
                      <Badge bg={getLockRateColor(player.lock_success_rate)} className="fs-6">
                        {formatPercentage(player.lock_success_rate)}
                      </Badge>
                    </div>
                  </div>

                  {/* Additional Stats */}
                  <div className="border-top pt-2">
                    <Row className="text-center">
                      <Col xs={6}>
                        <div className="text-muted" style={{ fontSize: '0.8rem' }}>Total Points</div>
                        <div className="fw-bold" style={{ fontSize: '1.1rem' }}>{player.total_points}</div>
                      </Col>
                      <Col xs={6}>
                        <div className="text-muted" style={{ fontSize: '0.8rem' }}>Avg Pts/Pick</div>
                        <div className="fw-bold" style={{ fontSize: '1.1rem' }}>{player.avg_points_per_pick}</div>
                      </Col>
                    </Row>
                  </div>
                </Card.Body>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* Mobile-specific styles */}
      <style>{`
        @media (max-width: 767.98px) {
          .stats-modal .modal-header {
            padding: 1rem !important;
          }
          .stats-modal .modal-title {
            font-size: 1rem !important;
          }
          .stats-modal .modal-body {
            padding: 1rem !important;
            max-height: calc(100vh - 100px) !important;
          }
          .stats-modal .modal-footer {
            padding: 0.5rem !important;
          }
          .stats-modal h6 {
            font-size: 0.75rem !important;
            margin-bottom: 0.5rem !important;
          }
          .stats-modal .card-body {
            padding: 0.5rem !important;
          }
          .stats-modal .streak-number {
            font-size: 1.25rem !important;
          }
          .stats-modal .badge {
            font-size: 0.6rem !important;
            padding: 0.15rem 0.4rem !important;
          }
          .stats-modal small {
            font-size: 0.65rem !important;
          }
          .stats-modal .team-name {
            font-size: 0.85rem !important;
          }
          .stats-modal .game-info {
            font-size: 0.75rem !important;
          }
          .stats-modal .points-value {
            font-size: 0.85rem !important;
          }
          .stats-modal .progress {
            height: 4px !important;
          }
          .stats-modal .mb-section {
            margin-bottom: 0.75rem !important;
          }
          .stats-modal .mb-card {
            margin-bottom: 0.25rem !important;
          }
          .stats-modal .icon-size {
            font-size: 1.2rem !important;
          }
        }
      `}</style>
      {/* Detailed Stats Modal */}
      <Modal 
        show={showModal} 
        onHide={handleCloseModal} 
        size="xl" 
        fullscreen="md-down" 
        centered
        className="stats-modal"
      >
        <Modal.Header 
          closeButton 
          className="border-bottom-0 py-3 py-md-4 bg-light"
        >
          <Modal.Title className="d-flex align-items-center">
            <FaChartLine className="me-2 me-md-3 text-primary icon-size" style={{ fontSize: '1.5rem' }} />
            <div>
              <div className="fw-bold" style={{ fontSize: '1.25rem' }}>
                {selectedPlayer?.full_name}'s Detailed Stats
              </div>
            </div>
          </Modal.Title>
        </Modal.Header>
        <Modal.Body className="p-3 p-md-4" style={{ maxHeight: 'calc(100vh - 120px)', overflowY: 'auto' }}>
          {loadingDetails ? (
            <div className="text-center py-3 py-md-4">
              <div className="spinner-border text-primary" role="status" style={{ width: 'clamp(2rem, 4vw, 2.5rem)', height: 'clamp(2rem, 4vw, 2.5rem)' }}>
                <span className="visually-hidden">Loading...</span>
              </div>
              <div className="mt-2 small">Loading detailed stats...</div>
            </div>
          ) : playerDetails ? (
            <div>
              {/* Show message if no data */}
              {(!playerDetails.favorite_teams || playerDetails.favorite_teams.length === 0) &&
               !playerDetails.least_favorite_team &&
               (!playerDetails.current_streak || playerDetails.current_streak.result === 'N/A') &&
               (!playerDetails.best_streak || playerDetails.best_streak.streak_length === 0) &&
               (!playerDetails.worst_streak || playerDetails.worst_streak.streak_length === 0) &&
               (!playerDetails.best_game && !playerDetails.worst_game) &&
               (!playerDetails.best_week && !playerDetails.worst_week) && (
                <Alert variant="info" className="text-center">
                  <strong>No detailed statistics available yet.</strong>
                  <br />
                  <small>This player hasn't made any picks.</small>
                </Alert>
              )}

              {/* Streaks Section - Enhanced */}
              {(playerDetails.current_streak || playerDetails.best_streak || playerDetails.worst_streak) && (
                <div className="mb-section mb-md-3">
                  <h6 className="mb-1 mb-md-2 fw-bold text-dark" style={{ fontSize: '1rem' }}>Streak Performance</h6>
                  <Row className="g-1 g-md-2">
                    {playerDetails.current_streak && playerDetails.current_streak.result !== 'N/A' && (
                      <Col xs={12} md={4}>
                        <Card 
                          className="h-100 shadow-sm border-0"
                          style={{
                            backgroundColor: playerDetails.current_streak.result === 'W' 
                              ? '#f0f9f4'
                              : playerDetails.current_streak.result === 'P'
                              ? '#fffbf0'
                              : '#fef0f0',
                            borderLeft: `4px solid ${
                              playerDetails.current_streak.result === 'W' ? '#28a745' :
                              playerDetails.current_streak.result === 'P' ? '#ffc107' : '#dc3545'
                            } !important`
                          }}
                        >
                          <Card.Body className="p-1 p-md-2">
                            <div className="d-flex align-items-center mb-card mb-md-2">
                              <FaFire 
                                className="me-1 icon-size" 
                                style={{ 
                                  fontSize: '1rem',
                                  color: playerDetails.current_streak.result === 'W' ? '#28a745' : '#dc3545'
                                }} 
                              />
                              <small className="fw-semibold text-muted" style={{ fontSize: '0.85rem' }}>Current Streak</small>
                            </div>
                            <div className="text-center">
                              <div 
                                className="fw-bold mb-1 streak-number"
                                style={{ 
                                  fontSize: '2rem',
                                  lineHeight: '1',
                                  color: playerDetails.current_streak.result === 'W' ? '#28a745' :
                                         playerDetails.current_streak.result === 'P' ? '#ffc107' : '#dc3545'
                                }}
                              >
                                {playerDetails.current_streak.streak_length}
                              </div>
                              <Badge
                                bg={playerDetails.current_streak.result === 'W' ? 'success' :
                                    playerDetails.current_streak.result === 'P' ? 'warning' : 'danger'}
                                className="px-1 px-md-2 py-0 py-md-1"
                                style={{ fontSize: '0.75rem' }}
                              >
                                {playerDetails.current_streak.result === 'W' ? 'Wins' :
                                 playerDetails.current_streak.result === 'P' ? 'Pushes' : 'Losses'}
                              </Badge>
                            </div>
                          </Card.Body>
                        </Card>
                      </Col>
                    )}
                    {playerDetails.best_streak && playerDetails.best_streak.streak_length > 0 && (
                      <Col xs={12} md={4}>
                        <Card 
                          className="h-100 shadow-sm border-0"
                          style={{
                            backgroundColor: '#f0f9f4',
                            borderLeft: '4px solid #28a745 !important'
                          }}
                        >
                          <Card.Body className="p-1 p-md-2">
                            <div className="d-flex align-items-center mb-card mb-md-2">
                              <FaArrowUp className="me-1 text-success icon-size" style={{ fontSize: '1rem' }} />
                              <small className="fw-semibold text-muted" style={{ fontSize: '0.85rem' }}>Best Streak</small>
                            </div>
                            <div className="text-center">
                              <div className="fw-bold mb-1 streak-number" style={{ fontSize: '2rem', lineHeight: '1', color: '#28a745' }}>
                                {playerDetails.best_streak.streak_length}
                              </div>
                              <Badge bg="success" className="px-1 px-md-2 py-0 py-md-1" style={{ fontSize: '0.75rem' }}>
                                Consecutive Wins
                              </Badge>
                            </div>
                          </Card.Body>
                        </Card>
                      </Col>
                    )}
                    {playerDetails.worst_streak && playerDetails.worst_streak.streak_length > 0 && (
                      <Col xs={12} md={4}>
                        <Card 
                          className="h-100 shadow-sm border-0"
                          style={{
                            backgroundColor: '#fef0f0',
                            borderLeft: '4px solid #dc3545 !important'
                          }}
                        >
                          <Card.Body className="p-1 p-md-2">
                            <div className="d-flex align-items-center mb-card mb-md-2">
                              <FaArrowDown className="me-1 text-danger icon-size" style={{ fontSize: '1rem' }} />
                              <small className="fw-semibold text-muted" style={{ fontSize: '0.85rem' }}>Worst Streak</small>
                            </div>
                            <div className="text-center">
                              <div className="fw-bold mb-1 streak-number" style={{ fontSize: '2rem', lineHeight: '1', color: '#dc3545' }}>
                                {playerDetails.worst_streak.streak_length}
                              </div>
                              <Badge bg="danger" className="px-1 px-md-2 py-0 py-md-1" style={{ fontSize: '0.75rem' }}>
                                Consecutive Losses
                              </Badge>
                            </div>
                          </Card.Body>
                        </Card>
                      </Col>
                    )}
                  </Row>
                </div>
              )}

              {/* Favorite Team and Least Favorite Team - Enhanced */}
              <div className="mb-section mb-md-3">
                <h6 className="mb-1 mb-md-2 fw-bold text-dark" style={{ fontSize: '1rem' }}>Team Preferences</h6>
                <Row className="g-1 g-md-2">
                  {playerDetails.favorite_teams && playerDetails.favorite_teams.length > 0 && (
                    <Col xs={12} md={6}>
                      <Card className="h-100 shadow-sm border-0" style={{ borderLeft: '4px solid #dc3545 !important' }}>
                        <Card.Body className="p-1 p-md-2">
                          <div className="d-flex align-items-center justify-content-between mb-card mb-md-2">
                            <small className="d-flex align-items-center mb-0 fw-semibold" style={{ fontSize: '0.85rem' }}>
                              <FaHeart className="me-1 text-danger icon-size" style={{ fontSize: '0.9rem' }} />
                              Favorite Team
                            </small>
                          </div>
                          <div className="mb-card mb-md-2">
                            <div className="fw-bold mb-1 team-name" style={{ fontSize: '1.1rem' }}>
                              {playerDetails.favorite_teams[0].picked_team}
                            </div>
                            <div className="small text-muted mb-1 mb-md-2" style={{ fontSize: '0.85rem' }}>
                              Picked <strong>{playerDetails.favorite_teams[0].pick_count}</strong> times
                            </div>
                            <div className="d-flex align-items-center">
                              <span className="small text-muted me-1 me-md-2" style={{ fontSize: '0.8rem' }}>Success:</span>
                              <span className="fw-bold me-1 me-md-2" style={{ color: '#28a745', fontSize: '0.875rem' }}>
                                {playerDetails.favorite_teams[0].success_rate || 0}%
                              </span>
                              <ProgressBar
                                now={playerDetails.favorite_teams[0].success_rate || 0}
                                variant="success"
                                className="flex-grow-1"
                                style={{ height: '6px' }}
                              />
                            </div>
                          </div>
                        </Card.Body>
                      </Card>
                    </Col>
                  )}
                  {playerDetails.least_favorite_team && (
                    <Col xs={12} md={6}>
                      <Card className="h-100 shadow-sm border-0" style={{ borderLeft: '4px solid #6c757d !important' }}>
                        <Card.Body className="p-1 p-md-2">
                          <div className="d-flex align-items-center justify-content-between mb-card mb-md-2">
                            <small className="d-flex align-items-center mb-0 fw-semibold" style={{ fontSize: '0.85rem' }}>
                              <FaHeart
                                className="me-1 text-muted icon-size"
                                style={{ fontSize: '0.9rem', transform: 'rotate(180deg)' }}
                              />
                              Least Favorite Team
                            </small>
                          </div>
                          <div className="mb-card mb-md-2">
                            <div className="fw-bold mb-1 team-name" style={{ fontSize: '1.1rem' }}>
                              {playerDetails.least_favorite_team.picked_against_team}
                            </div>
                            <div className="small text-muted mb-1 mb-md-2" style={{ fontSize: '0.85rem' }}>
                              Picked against <strong>{playerDetails.least_favorite_team.pick_count}</strong> times
                            </div>
                            <div className="d-flex align-items-center">
                              <span className="small text-muted me-1 me-md-2" style={{ fontSize: '0.8rem' }}>Success:</span>
                              <span className="fw-bold me-1 me-md-2" style={{ color: '#28a745', fontSize: '0.875rem' }}>
                                {playerDetails.least_favorite_team.success_rate || 0}%
                              </span>
                              <ProgressBar
                                now={playerDetails.least_favorite_team.success_rate || 0}
                                variant="success"
                                className="flex-grow-1"
                                style={{ height: '6px' }}
                              />
                            </div>
                          </div>
                        </Card.Body>
                      </Card>
                    </Col>
                  )}
                </Row>
              </div>

              {/* Weekly Performance - Best and Worst Weeks */}
              {(playerDetails.best_week || playerDetails.worst_week) && (
                <div className="mb-section mb-md-3">
                  <h6 className="mb-1 mb-md-2 fw-bold text-dark" style={{ fontSize: '1rem' }}>Weekly Performance</h6>
                  <Row className="g-1 g-md-2">
                    {playerDetails.best_week && (
                      <Col xs={12} md={6}>
                        <Card
                          className="h-100 shadow-sm border-0"
                          style={{
                            backgroundColor: '#f0f9f4',
                            borderLeft: '4px solid #28a745 !important'
                          }}
                        >
                          <Card.Body className="p-1 p-md-2">
                            <div className="d-flex align-items-center mb-card mb-md-2">
                              <FaChartLine className="me-1 text-success icon-size" style={{ fontSize: '0.9rem' }} />
                              <small className="fw-semibold text-success" style={{ fontSize: '0.85rem' }}>Best Week</small>
                            </div>
                            <div className="mb-card mb-md-2">
                              <div className="fw-bold mb-1" style={{ fontSize: '1.1rem', color: '#155724' }}>
                                {playerDetails.best_week.week_label}
                              </div>
                              <div className="small text-muted mb-1" style={{ fontSize: '0.8rem' }}>
                                {new Date(playerDetails.best_week.week_start).toLocaleDateString('en-US', {
                                  month: 'short',
                                  day: 'numeric'
                                })} - {new Date(playerDetails.best_week.week_end).toLocaleDateString('en-US', {
                                  month: 'short',
                                  day: 'numeric',
                                  year: 'numeric'
                                })}
                              </div>
                              <div className="d-flex align-items-center justify-content-between mb-1">
                                <span className="small text-muted" style={{ fontSize: '0.8rem' }}>Total Points:</span>
                                <span className="fw-bold" style={{ color: '#28a745', fontSize: '1rem' }}>
                                  {playerDetails.best_week.total_points}
                                </span>
                              </div>
                              <div className="d-flex align-items-center justify-content-between">
                                <span className="small text-muted" style={{ fontSize: '0.8rem' }}>Win Rate:</span>
                                <span className="fw-bold" style={{ color: '#28a745', fontSize: '0.875rem' }}>
                                  {playerDetails.best_week.win_percentage}%
                                </span>
                              </div>
                              <div className="mt-1 small text-muted" style={{ fontSize: '0.75rem' }}>
                                {playerDetails.best_week.correct_picks}/{playerDetails.best_week.total_picks} correct
                                {playerDetails.best_week.locks_used > 0 && (
                                  <span className="ms-1">
                                    • {playerDetails.best_week.locks_used} lock{playerDetails.best_week.locks_used !== 1 ? 's' : ''} used
                                  </span>
                                )}
                              </div>
                            </div>
                          </Card.Body>
                        </Card>
                      </Col>
                    )}
                    {playerDetails.worst_week && (
                      <Col xs={12} md={6}>
                        <Card
                          className="h-100 shadow-sm border-0"
                          style={{
                            backgroundColor: '#fef0f0',
                            borderLeft: '4px solid #dc3545 !important'
                          }}
                        >
                          <Card.Body className="p-1 p-md-2">
                            <div className="d-flex align-items-center mb-card mb-md-2">
                              <FaArrowDown className="me-1 text-danger icon-size" style={{ fontSize: '0.9rem' }} />
                              <small className="fw-semibold text-danger" style={{ fontSize: '0.85rem' }}>Worst Week</small>
                            </div>
                            <div className="mb-card mb-md-2">
                              <div className="fw-bold mb-1" style={{ fontSize: '1.1rem', color: '#721c24' }}>
                                {playerDetails.worst_week.week_label}
                              </div>
                              <div className="small text-muted mb-1" style={{ fontSize: '0.8rem' }}>
                                {new Date(playerDetails.worst_week.week_start).toLocaleDateString('en-US', {
                                  month: 'short',
                                  day: 'numeric'
                                })} - {new Date(playerDetails.worst_week.week_end).toLocaleDateString('en-US', {
                                  month: 'short',
                                  day: 'numeric',
                                  year: 'numeric'
                                })}
                              </div>
                              <div className="d-flex align-items-center justify-content-between mb-1">
                                <span className="small text-muted" style={{ fontSize: '0.8rem' }}>Total Points:</span>
                                <span className="fw-bold" style={{ color: '#dc3545', fontSize: '1rem' }}>
                                  {playerDetails.worst_week.total_points}
                                </span>
                              </div>
                              <div className="d-flex align-items-center justify-content-between">
                                <span className="small text-muted" style={{ fontSize: '0.8rem' }}>Win Rate:</span>
                                <span className="fw-bold" style={{ color: '#dc3545', fontSize: '0.875rem' }}>
                                  {playerDetails.worst_week.win_percentage}%
                                </span>
                              </div>
                              <div className="mt-1 small text-muted" style={{ fontSize: '0.75rem' }}>
                                {playerDetails.worst_week.correct_picks}/{playerDetails.worst_week.total_picks} correct
                                {playerDetails.worst_week.locks_used > 0 && (
                                  <span className="ms-1">
                                    • {playerDetails.worst_week.locks_used} lock{playerDetails.worst_week.locks_used !== 1 ? 's' : ''} used
                                  </span>
                                )}
                              </div>
                            </div>
                          </Card.Body>
                        </Card>
                      </Col>
                    )}
                  </Row>
                </div>
              )}

              {/* Best Game and Worst Game - Enhanced */}
              {(playerDetails.best_game || playerDetails.worst_game) && (
                <div className="mb-section mb-md-2">
                  <h6 className="mb-1 mb-md-2 fw-bold text-dark" style={{ fontSize: '1rem' }}>Notable Games</h6>
                  <Row className="g-1 g-md-2">
                    {playerDetails.best_game && (
                      <Col xs={12} md={6}>
                        <Card 
                          className="h-100 shadow-sm border-0"
                          style={{
                            backgroundColor: '#f0f9f4',
                            borderLeft: '4px solid #28a745 !important'
                          }}
                        >
                          <Card.Body className="p-1 p-md-2">
                            <div className="d-flex align-items-center mb-card mb-md-2">
                              <FaTrophy className="me-1 text-warning icon-size" style={{ fontSize: '0.9rem' }} />
                              <small className="fw-semibold text-success" style={{ fontSize: '0.85rem' }}>Best Game</small>
                            </div>
                            <div className="mb-card mb-md-2">
                              <div className="fw-bold mb-1 game-info" style={{ fontSize: '1rem', color: '#155724' }}>
                                {playerDetails.best_game.away_team} @ {playerDetails.best_game.home_team}
                              </div>
                              <div className="small text-muted mb-1" style={{ fontSize: '0.8rem' }}>
                                <span className="fw-semibold">Picked:</span> {playerDetails.best_game.picked_team}
                                <span className="mx-1">•</span>
                                {new Date(playerDetails.best_game.game_date).toLocaleDateString('en-US', { 
                                  month: 'short', 
                                  day: 'numeric', 
                                  year: 'numeric' 
                                })}
                              </div>
                            </div>
                            <div className="d-flex justify-content-between align-items-center pt-1 pt-md-2 border-top">
                              <div className="d-flex align-items-center">
                                <span 
                                  className="fw-bold me-1 points-value" 
                                  style={{ fontSize: '1.1rem', color: '#28a745' }}
                                >
                                  {playerDetails.best_game.points_awarded}
                                </span>
                                <span className="text-muted small me-1" style={{ fontSize: '0.8rem' }}>
                                  {playerDetails.best_game.points_awarded === 1 ? 'pt' : 'pts'}
                                </span>
                                {playerDetails.best_game.lock && (
                                  <FaLock size={10} className="text-dark" title="Locked pick" />
                                )}
                              </div>
                              <Badge bg="success" className="px-1 px-md-2 py-0 py-md-1" style={{ fontSize: '0.75rem' }}>
                                Only {playerDetails.best_game.consensus_count} agreed
                              </Badge>
                            </div>
                          </Card.Body>
                        </Card>
                      </Col>
                    )}
                    {playerDetails.worst_game && (
                      <Col xs={12} md={6}>
                        <Card 
                          className="h-100 shadow-sm border-0"
                          style={{
                            backgroundColor: '#fef0f0',
                            borderLeft: '4px solid #dc3545 !important'
                          }}
                        >
                          <Card.Body className="p-1 p-md-2">
                            <div className="d-flex align-items-center mb-card mb-md-2">
                              <FaArrowDown className="me-1 text-danger icon-size" style={{ fontSize: '0.9rem' }} />
                              <small className="fw-semibold text-danger" style={{ fontSize: '0.85rem' }}>Worst Game</small>
                            </div>
                            <div className="mb-card mb-md-2">
                              <div className="fw-bold mb-1 game-info" style={{ fontSize: '1rem', color: '#721c24' }}>
                                {playerDetails.worst_game.away_team} @ {playerDetails.worst_game.home_team}
                              </div>
                              <div className="small text-muted mb-1" style={{ fontSize: '0.8rem' }}>
                                <span className="fw-semibold">Picked:</span> {playerDetails.worst_game.picked_team}
                                <span className="mx-1">•</span>
                                {new Date(playerDetails.worst_game.game_date).toLocaleDateString('en-US', { 
                                  month: 'short', 
                                  day: 'numeric', 
                                  year: 'numeric' 
                                })}
                              </div>
                            </div>
                            <div className="d-flex justify-content-between align-items-center pt-1 pt-md-2 border-top">
                              <div className="d-flex align-items-center">
                                <span 
                                  className="fw-bold me-1 points-value" 
                                  style={{ fontSize: '1.1rem', color: '#dc3545' }}
                                >
                                  {playerDetails.worst_game.points_awarded}
                                </span>
                                <span className="text-muted small me-1" style={{ fontSize: '0.8rem' }}>
                                  {playerDetails.worst_game.points_awarded === 1 ? 'pt' : 'pts'}
                                </span>
                                {playerDetails.worst_game.lock && (
                                  <FaLock size={10} className="text-dark" title="Locked pick" />
                                )}
                              </div>
                              <Badge bg="danger" className="px-1 px-md-2 py-0 py-md-1" style={{ fontSize: '0.75rem' }}>
                                {playerDetails.worst_game.against_count} picked against
                              </Badge>
                            </div>
                          </Card.Body>
                        </Card>
                      </Col>
                    )}
                  </Row>
                </div>
              )}
            </div>
          ) : (
            <Alert variant="warning" className="text-center">
              <strong>Failed to load detailed statistics</strong>
              <br />
              <small>This could be due to a server error or network issue. Please try again later.</small>
            </Alert>
          )}
        </Modal.Body>
        <Modal.Footer className="border-top-0 py-1 py-md-2">
          <button 
            className="btn btn-primary w-100 w-md-auto px-3 px-md-4" 
            onClick={handleCloseModal}
            style={{ minHeight: '38px', fontSize: '1rem' }}
          >
            Close
          </button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}