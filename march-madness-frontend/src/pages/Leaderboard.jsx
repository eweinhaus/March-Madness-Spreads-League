import { useEffect, useState } from "react";
import { Alert, Modal, Button, Table, Form, Accordion } from "react-bootstrap";
import { FaLock } from "react-icons/fa";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { groupPicksByTournamentHalf } from "../utils/etLockDay";

export default function Leaderboard() {
  const [leaderboard, setLeaderboard] = useState([]);
  const [error, setError] = useState(null);
  const [selectedUser, setSelectedUser] = useState(null);
  const [selectedUserDisplayName, setSelectedUserDisplayName] = useState(null);
  const [userPicks, setUserPicks] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [filter, setFilter] = useState('overall');
  const [weekOptions, setWeekOptions] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    fetchWeekOptions();
  }, []);

  useEffect(() => {
    fetchLeaderboard();
  }, [filter]);

  const fetchWeekOptions = () => {
    api.get('/leaderboard/weeks')
      .then(res => {
        setWeekOptions(res.data.weeks);
      })
      .catch(err => {
        console.error('Failed to load week options:', err);
        setWeekOptions([
          { key: "overall", label: "Overall" },
          { key: "first_half", label: "First Half (through Mar 23)" },
          { key: "second_half", label: "Second Half (Mar 24+)" },
        ]);
      });
  };

  const fetchLeaderboard = () => {
    api.get(`/leaderboard?filter=${filter}`)
      .then(res => {
        setLeaderboard(res.data);
        setError(null);
      })
      .catch(err => {
        if (err.response?.status === 401) {
          navigate('/login');
          return;
        }
        console.error('Leaderboard fetch error:', err);
        setError('Failed to load leaderboard. Please try again.');
      });
  };

  const handleUserClick = async (uid) => {
    try {
      const response = await api.get(`/user_all_past_picks/${uid}?filter=${filter}`);

      const userInfo = leaderboard.find(player => player.uid === uid);
      setSelectedUserDisplayName(userInfo?.display_name || uid);

      setUserPicks({
        picks: response.data.game_picks,
        tiebreakers: response.data.tiebreaker_picks
      });
      setSelectedUser(uid);
      setShowModal(true);
    } catch (err) {
      if (err.response?.status === 401) {
        navigate('/login');
        return;
      }
      if (err.response?.status === 404) {
        console.log('User not found or does not have permission to make picks');
      } else {
        console.error(err);
      }
    }
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setSelectedUser(null);
    setSelectedUserDisplayName(null);
    setUserPicks([]);
  };

  return (
    <div className="container my-3 my-md-5 px-2 px-md-3">
      <div className="d-flex justify-content-between align-items-center mb-3 mb-md-4">
        <h2 className="mb-0 text-center text-md-start">Leaderboard</h2>
        <Form.Select 
          className="w-auto" 
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          {weekOptions.map((week) => (
            <option key={week.key} value={week.key}>
              {week.label}
            </option>
          ))}
        </Form.Select>
      </div>
      
      {error && (
        <Alert variant="danger" className="mb-3 mb-md-4">
          {error}
        </Alert>
      )}
      
      {leaderboard.length === 0 && !error ? (
        <Alert variant="info">
          Loading leaderboard...
        </Alert>
      ) : (
        <ul className="list-group shadow-sm">
          {leaderboard.map((player, index) => (
            <li 
              key={player.uid} 
              className="list-group-item d-flex justify-content-between align-items-center py-3"
              style={{ cursor: 'pointer' }}
              onClick={() => handleUserClick(player.uid)}
            >
              <div>
                {index + 1}. {player.display_name}
              </div>
              <div className="d-flex align-items-center gap-2">
                <span className="badge bg-primary rounded-pill">
                  {player.total_points} points
                </span>
                <span className="badge bg-warning text-dark rounded-pill d-flex align-items-center gap-1" style={{ fontSize: '0.75rem' }}>
                  {player.correct_locks} <FaLock className="text-dark" size={10} />
                  </span>
                {filter !== 'overall' && player.first_tiebreaker_diff !== 999999 && (
                  <span className="badge bg-info rounded-pill" style={{ fontSize: '0.75rem' }}>
                    TB1: {player.first_tiebreaker_diff}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal show={showModal} onHide={handleCloseModal} size="lg" centered fullscreen="sm-down">
        <Modal.Header closeButton>
          <Modal.Title>{selectedUserDisplayName}'s Picks</Modal.Title>
        </Modal.Header>
        <Modal.Body className="p-2 p-md-3">
          {(!userPicks.picks || userPicks.picks.length === 0) && (!userPicks.tiebreakers || userPicks.tiebreakers.length === 0) ? (
            <Alert variant="info">
              No picks available for this time period
            </Alert>
          ) : (
            <>
              {userPicks.picks && userPicks.picks.length > 0 && (
                <>
                  {filter === 'overall' ? (
                    <Accordion defaultActiveKey="" className="mb-4">
                      {Object.values(groupPicksByTournamentHalf(userPicks.picks))
                        .filter((half) => half.picks.length > 0)
                        .map((halfData) => (
                          <Accordion.Item key={halfData.key} eventKey={halfData.key}>
                            <Accordion.Header>
                              {halfData.label} ({halfData.picks.length} pick{halfData.picks.length !== 1 ? 's' : ''})
                            </Accordion.Header>
                            <Accordion.Body className="p-2">
                              <div className="table-responsive">
                                <Table striped bordered hover responsive className="mb-0" size="sm">
                                  <thead>
                                    <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
                                      <th className="py-2">Game</th>
                                      <th className="py-2">Pick</th>
                                    </tr>
                                  </thead>
                                  <tbody className="small">
                                    {halfData.picks
                                      .sort((a, b) => new Date(b.game_date) - new Date(a.game_date))
                                      .map((pick) => {
                                        let pickCellClass = "";
                                        if (pick.winning_team && pick.winning_team !== "PUSH") {
                                          const normalizeTeamName = (name) => name?.replace(/[\s*]+$/, '');
                                          const isCorrectPick = normalizeTeamName(pick.winning_team) === normalizeTeamName(pick.picked_team);
                                          pickCellClass = isCorrectPick ? "table-success" : "table-danger";
                                        } else if (pick.winning_team === "PUSH") {
                                          pickCellClass = "table-warning";
                                        }

                                        return (
                                          <tr key={pick.game_id} style={{ fontSize: '0.85rem', lineHeight: '1.2' }}>
                                            <td className="text-nowrap py-2">
                                              {pick.spread < 0
                                                ? `${pick.away_team} @ ${pick.home_team} +${Math.abs(pick.spread)}`
                                                : `${pick.away_team} @ ${pick.home_team} -${pick.spread}`}
                                            </td>
                                            <td className={`py-2 ${pickCellClass}`} style={{
                                              ...(pick.lock && {
                                                border: `3px solid ${
                                                  !pick.winning_team || pick.winning_team === ''
                                                    ? '#000000'
                                                    : (() => {
                                                        if (pick.winning_team === "PUSH") return '#8B0000';
                                                        const normalizeTeamName = (name) => name?.replace(/[\s*]+$/, '');
                                                        const isCorrectPick = normalizeTeamName(pick.winning_team) === normalizeTeamName(pick.picked_team);
                                                        return isCorrectPick ? '#006400' : '#8B0000';
                                                      })()
                                                }`,
                                                borderRadius: '6px',
                                                position: 'relative'
                                              })
                                            }}>
                                              <div className="d-flex align-items-center gap-2">
                                                {!pick.picked_team ? <span className="fst-italic text-muted">No pick submitted</span> :
                                                  (() => {
                                                    const normalizeTeamName = (name) => name?.replace(/[\s*]+$/, '');
                                                    const isHomeTeam = normalizeTeamName(pick.picked_team) === normalizeTeamName(pick.home_team);

                                                    return isHomeTeam
                                                      ? `${pick.picked_team} ${pick.spread < 0 ? `+${Math.abs(pick.spread)}` : `-${pick.spread}`}`
                                                      : `${pick.picked_team} ${pick.spread < 0 ? `-${Math.abs(pick.spread)}` : `+${pick.spread}`}`
                                                  })()
                                                }
                                                {pick.lock && (
                                                  <FaLock className="text-dark" size={14} title="Lock of the day" />
                                                )}
                                                {pick.winning_team === "PUSH" && (
                                                  <span className="badge bg-secondary" style={{ fontSize: '0.75rem', padding: '0.2em 0.4em' }}>PUSH</span>
                                                )}
                                              </div>
                                            </td>
                                          </tr>
                                        );
                                      })}
                                  </tbody>
                                </Table>
                              </div>
                            </Accordion.Body>
                          </Accordion.Item>
                        ))}

                        {userPicks.tiebreakers && userPicks.tiebreakers.length > 0 && (
                          <Accordion.Item eventKey="questions">
                            <Accordion.Header>
                              Questions ({userPicks.tiebreakers.length} answer{userPicks.tiebreakers.length !== 1 ? 's' : ''})
                            </Accordion.Header>
                            <Accordion.Body className="p-2">
                              <div className="table-responsive">
                                <Table striped bordered hover responsive className="mb-0" size="sm">
                                  <thead>
                                    <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
                                      <th className="py-2">Question</th>
                                      <th className="py-2">Pick</th>
                                      <th className="py-2">Accuracy</th>
                                    </tr>
                                  </thead>
                                  <tbody className="small">
                                    {userPicks.tiebreakers
                                      .filter(tiebreaker => {
                                        const tiebreakerDate = new Date(tiebreaker.start_time);
                                        const revealTime = new Date(tiebreakerDate);
                                        revealTime.setHours(18, 10, 0, 0);
                                        return new Date() >= revealTime;
                                      })
                                      .sort((a, b) => new Date(b.start_time) - new Date(a.start_time))
                                      .map((tiebreaker) => {
                                      const hasPoints = tiebreaker.points_awarded && tiebreaker.points_awarded > 0;
                                      const rowClass = hasPoints ? "table-success" : "";

                                      return (
                                        <tr key={tiebreaker.tiebreaker_id} className={rowClass} style={{ fontSize: '0.85rem', lineHeight: '1.2' }}>
                                          <td className="py-2">{tiebreaker.question}</td>
                                          <td className="py-2">
                                            {tiebreaker.user_answer !== null && tiebreaker.user_answer !== undefined
                                              ? tiebreaker.user_answer
                                              : <span className="text-muted">No Answer</span>}
                                            {tiebreaker.correct_answer && !["N/A", "NA", "n/a", "na", "Na"].includes(tiebreaker.correct_answer) && (
                                              <span className="text-muted ms-2" style={{ fontSize: '0.8rem' }}>
                                                (Correct: {tiebreaker.correct_answer})
                                              </span>
                                            )}
                                          </td>
                                          <td className="py-2 text-center">
                                            {tiebreaker.accuracy_diff !== null ? (
                                              <span className="badge bg-info" style={{ fontSize: '0.75rem', padding: '0.2em 0.4em' }}>
                                                {tiebreaker.accuracy_diff}
                                              </span>
                                            ) : (
                                              <span className="text-muted" style={{ fontSize: '0.75rem' }}>-</span>
                                            )}
                                          </td>
                                        </tr>
                                      );
                                    })}
                                  </tbody>
                                </Table>
                              </div>
                            </Accordion.Body>
                          </Accordion.Item>
                        )}
                    </Accordion>
                  ) : (
                    <div className="table-responsive mb-4">
                      <Table striped bordered hover responsive className="mb-0" size="sm">
                        <thead>
                          <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
                            <th className="py-2">Game</th>
                            <th className="py-2">Pick</th>
                          </tr>
                        </thead>
                        <tbody className="small">
                          {userPicks.picks
                            .sort((a, b) => new Date(b.game_date) - new Date(a.game_date))
                            .map((pick) => {

                            let pickCellClass = "";
                            if (pick.winning_team && pick.winning_team !== "PUSH") {
                              const normalizeTeamName = (name) => name?.replace(/[\s*]+$/, '');
                              const isCorrectPick = normalizeTeamName(pick.winning_team) === normalizeTeamName(pick.picked_team);
                              pickCellClass = isCorrectPick ? "table-success" : "table-danger";
                            } else if (pick.winning_team === "PUSH") {
                              pickCellClass = "table-warning";
                            }

                            return (
                              <tr key={pick.game_id} style={{ fontSize: '0.85rem', lineHeight: '1.2' }}>
                                <td className="text-nowrap py-2">
                                  {pick.spread < 0
                                    ? `${pick.away_team} @ ${pick.home_team} +${Math.abs(pick.spread)}`
                                    : `${pick.away_team} @ ${pick.home_team} -${pick.spread}`}
                                </td>
                                <td className={`py-2 ${pickCellClass}`} style={{
                                  ...(pick.lock && {
                                    border: `3px solid ${
                                      !pick.winning_team || pick.winning_team === ''
                                        ? '#000000'
                                        : (() => {
                                            if (pick.winning_team === "PUSH") return '#8B0000';
                                            const normalizeTeamName = (name) => name?.replace(/[\s*]+$/, '');
                                            const isCorrectPick = normalizeTeamName(pick.winning_team) === normalizeTeamName(pick.picked_team);
                                            return isCorrectPick ? '#006400' : '#8B0000';
                                          })()
                                    }`,
                                    borderRadius: '6px',
                                    position: 'relative'
                                  })
                                }}>
                                  <div className="d-flex align-items-center gap-2">
                                    {!pick.picked_team ? <span className="fst-italic text-muted">No pick submitted</span> :
                                      (() => {
                                        const normalizeTeamName = (name) => name?.replace(/[\s*]+$/, '');
                                        const isHomeTeam = normalizeTeamName(pick.picked_team) === normalizeTeamName(pick.home_team);

                                        return isHomeTeam
                                          ? `${pick.picked_team} ${pick.spread < 0 ? `+${Math.abs(pick.spread)}` : `-${pick.spread}`}`
                                          : `${pick.picked_team} ${pick.spread < 0 ? `-${Math.abs(pick.spread)}` : `+${pick.spread}`}`
                                      })()
                                    }
                                    {pick.lock && (
                                      <FaLock className="text-dark" size={14} title="Lock of the day" />
                                    )}
                                  {pick.winning_team === "PUSH" && (
                                      <span className="badge bg-secondary" style={{ fontSize: '0.75rem', padding: '0.2em 0.4em' }}>PUSH</span>
                                  )}
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </Table>
                    </div>
                  )}
                </>
              )}

              {filter !== 'overall' && userPicks.tiebreakers && userPicks.tiebreakers.length > 0 && (
                <>
                  <div className="table-responsive">
                    <Table striped bordered hover responsive className="mb-0" size="sm">
                      <thead>
                                              <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
                        <th className="py-2">Question</th>
                        <th className="py-2">Pick</th>
                        <th className="py-2">Accuracy</th>
                      </tr>
                      </thead>
                      <tbody className="small">
                        {userPicks.tiebreakers
                          .filter(tiebreaker => {
                            const tiebreakerDate = new Date(tiebreaker.start_time);
                            const revealTime = new Date(tiebreakerDate);
                            revealTime.setHours(18, 10, 0, 0);
                            return new Date() >= revealTime;
                          })
                          .sort((a, b) => new Date(b.start_time) - new Date(a.start_time))
                          .map((tiebreaker) => {
                          const hasPoints = tiebreaker.points_awarded && tiebreaker.points_awarded > 0;
                          const rowClass = hasPoints ? "table-success" : "";
                          
                          return (
                            <tr key={tiebreaker.tiebreaker_id} className={rowClass} style={{ fontSize: '0.85rem', lineHeight: '1.2' }}>
                              <td className="py-2">{tiebreaker.question}</td>
                              <td className="py-2">
                                {tiebreaker.user_answer !== null && tiebreaker.user_answer !== undefined 
                                  ? tiebreaker.user_answer 
                                  : <span className="text-muted">No Answer</span>}
                                {tiebreaker.correct_answer && !["N/A", "NA", "n/a", "na", "Na"].includes(tiebreaker.correct_answer) && (
                                  <span className="text-muted ms-2" style={{ fontSize: '0.8rem' }}>
                                    (Correct: {tiebreaker.correct_answer})
                                  </span>
                                )}
                              </td>
                              <td className="py-2 text-center">
                                {tiebreaker.accuracy_diff !== null ? (
                                  <span className="badge bg-info" style={{ fontSize: '0.75rem', padding: '0.2em 0.4em' }}>
                                    {tiebreaker.accuracy_diff}
                                  </span>
                                ) : (
                                  <span className="text-muted" style={{ fontSize: '0.75rem' }}>-</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </Table>
                  </div>
                </>
              )}
            </>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={handleCloseModal}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}
