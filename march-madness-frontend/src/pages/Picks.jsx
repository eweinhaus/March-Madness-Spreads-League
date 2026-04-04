import { useEffect, useState, useMemo, useCallback } from "react";
import { Container, Row, Col, Card, Button, Alert, Form, Modal } from "react-bootstrap";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { sameLockDay, getLockDayBounds } from "../utils/etLockDay";

const NY_TZ = "America/New_York";

/** Must match backend PICK_LOCK_BEFORE_TIP (submit_pick, tiebreaker_picks). */
const PICKS_LOCK_MS_BEFORE_TIPOFF = 60_000;

/**
 * Lock-of-the-day UI (button, copy) and whether submit prompts for a lock per game day.
 * When false: users are not prompted or blocked for missing a lock; only games/questions warnings apply.
 * Temporary: hide lock controls without removing backend/state logic.
 */
const SHOW_LOCK_OF_THE_DAY_UI = false;

/** Inline so it works on Vercel (SPA rewrite serves HTML for /basketball.svg). */
function BasketballSpinnerIcon({ size = 56 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className="picks-check-spin"
    >
      <circle cx="16" cy="16" r="15" fill="#FF6B00" stroke="#000" strokeWidth="2" />
      <path
        d="M16 1C7.716 1 1 7.716 1 16s6.716 15 15 15 15-6.716 15-15S24.284 1 16 1z"
        stroke="#000"
        strokeWidth="2"
      />
      <path d="M16 1v30M1 16h30" stroke="#000" strokeWidth="2" />
      <path d="M8 8l16 16M24 8L8 24" stroke="#000" strokeWidth="2" />
    </svg>
  );
}

/** One getLockDayBounds() per unique game_date string (tip times often repeat). */
function getLockDayCached(iso, cache) {
  let row = cache.get(iso);
  if (!row) {
    const { dayStart } = getLockDayBounds(iso);
    row = {
      dayKey: dayStart.getTime(),
      label: dayStart.toLocaleDateString("en-US", {
        timeZone: NY_TZ,
        weekday: "short",
        month: "short",
        day: "numeric",
        year: "numeric",
      }),
    };
    cache.set(iso, row);
  }
  return row;
}

function tiebreakerIsAnswered(tid, tiebreakerPicks, existingTiebreakerPicks) {
  if (Object.prototype.hasOwnProperty.call(tiebreakerPicks, tid)) {
    const v = tiebreakerPicks[tid];
    if (v === null || v === undefined) return false;
    if (typeof v === "number" && Number.isNaN(v)) return false;
    if (typeof v === "string" && v.trim() === "") return false;
    return true;
  }
  const e = existingTiebreakerPicks[tid];
  if (e === null || e === undefined) return false;
  if (typeof e === "string" && e.trim() === "") return false;
  return true;
}

export default function Picks() {
  const [games, setGames] = useState([]);
  const [picks, setPicks] = useState({});
  const [existingPicks, setExistingPicks] = useState({});
  const [locks, setLocks] = useState({});
  const [existingLocks, setExistingLocks] = useState({});
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [tiebreakers, setTiebreakers] = useState([]);
  const [tiebreakerPicks, setTiebreakerPicks] = useState({});
  const [existingTiebreakerPicks, setExistingTiebreakerPicks] = useState({});
  const [showSubmitWarning, setShowSubmitWarning] = useState(false);
  const [submitWarnings, setSubmitWarnings] = useState({
    missingGames: [],
    missingLockDays: [],
    missingQuestions: [],
  });
  const [isCheckingWarnings, setIsCheckingWarnings] = useState(false);
  const navigate = useNavigate();

  const formatDateForDisplay = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      year: 'numeric', month: 'numeric', day: 'numeric',
      hour: 'numeric', minute: '2-digit', hour12: true
    });
  };

  const handleAuthError = (err) => {
    if (err.response && err.response.status === 401) {
      navigate('/login');
      return true;
    }
    return false;
  };

  useEffect(() => {
    setIsLoading(true);
    api.get('/picks_data')
      .then((response) => {
        const { games, tiebreakers } = response.data;
        setGames(games);

        const picksObj = {};
        const locksObj = {};
        games.forEach(game => {
          const gid = String(game.game_id);
          if (game.picked_team) picksObj[gid] = game.picked_team;
          if (game.lock) locksObj[gid] = game.lock;
        });
        setExistingPicks(picksObj);
        setExistingLocks(locksObj);

        setTiebreakers(tiebreakers);
        const tiebreakerPicksObj = {};
        tiebreakers.forEach(t => {
          const tid = String(t.tiebreaker_id);
          if (t.user_answer !== null && t.user_answer !== undefined) {
            tiebreakerPicksObj[tid] = t.user_answer;
          }
        });
        setExistingTiebreakerPicks(tiebreakerPicksObj);
        setIsLoading(false);
      })
      .catch(err => {
        if (!handleAuthError(err)) {
          if (err.response && err.response.status === 403) {
            setError('You do not have permission to make picks. Please contact an administrator.');
          } else {
            setError('Failed to load games, picks, and tiebreakers');
          }
        }
        setIsLoading(false);
      });
  }, [navigate]);

  const handlePick = useCallback((gameId, team) => {
    const gid = String(gameId);
    setPicks(prev => ({ ...prev, [gid]: team }));
  }, []);

  const handleTiebreakerPick = useCallback((tiebreakerId, answer, isNumeric = true) => {
    const tid = String(tiebreakerId);
    setTiebreakerPicks(prev => ({
      ...prev,
      [tid]: isNumeric ? parseFloat(answer) : answer
    }));
  }, []);

  const picksFrozenForGame = useCallback((gameDate) => {
    const tip = new Date(gameDate).getTime();
    return new Date().getTime() >= tip - PICKS_LOCK_MS_BEFORE_TIPOFF;
  }, []);

  const tiebreakerPickStillOpen = useCallback((startTime) => {
    const lockAt = new Date(startTime).getTime() - PICKS_LOCK_MS_BEFORE_TIPOFF;
    return new Date().getTime() < lockAt;
  }, []);

  const handleLockToggle = (gameId) => {
    const gid = String(gameId);
    const isCurrentlyLocked = locks[gid] !== undefined ? locks[gid] : (existingLocks[gid] || false);

    if (isCurrentlyLocked) {
      setLocks(prev => ({ ...prev, [gid]: false }));
    } else {
      const targetGame = games.find(g => String(g.game_id) === gid);
      if (!targetGame) { setError('Game not found'); return; }

      const allLocks = { ...existingLocks, ...locks };
      let startedLockedGameInSameDay = null;

      for (const [lockGid, isLocked] of Object.entries(allLocks)) {
        if (isLocked) {
          const lockGame = games.find(g => String(g.game_id) === lockGid);
          if (lockGame) {
            if (sameLockDay(lockGame.game_date, targetGame.game_date) && picksFrozenForGame(lockGame.game_date)) {
              startedLockedGameInSameDay = lockGame;
              break;
            }
          }
        }
      }

      if (startedLockedGameInSameDay) {
        setError(`Your locked game (${startedLockedGameInSameDay.away_team} @ ${startedLockedGameInSameDay.home_team}) has passed the pick cutoff (1 minute before tip) and cannot be changed.`);
        return;
      }

      const newLocks = { ...locks };

      const unlockSameLockDay = (lockSource) => {
        Object.keys(lockSource).forEach(id => {
          const game = games.find(g => String(g.game_id) === id);
          if (game && sameLockDay(game.game_date, targetGame.game_date)) newLocks[id] = false;
        });
      };
      unlockSameLockDay(newLocks);
      unlockSameLockDay(existingLocks);
      newLocks[gid] = true;
      setLocks(newLocks);
      setError(null);
    }
  };

  /** Single pass; cached lock-day bounds per unique tipoff string. */
  const computeSubmitWarnings = useCallback(
    (gameList, tbList) => {
      const missingGames = [];
      const dayBuckets = new Map();
      const boundsCache = new Map();

      for (const game of gameList) {
        const gid = String(game.game_id);
        if (!picks[gid] && !existingPicks[gid]) {
          missingGames.push({
            gid,
            label: `${game.away_team} @ ${game.home_team}`,
            time: formatDateForDisplay(game.game_date),
          });
        }

        if (SHOW_LOCK_OF_THE_DAY_UI) {
          const { dayKey, label } = getLockDayCached(game.game_date, boundsCache);
          let bucket = dayBuckets.get(dayKey);
          if (!bucket) {
            bucket = { label, games: [] };
            dayBuckets.set(dayKey, bucket);
          }
          bucket.games.push(game);
        }
      }

      const missingLockDays = [];
      if (SHOW_LOCK_OF_THE_DAY_UI) {
        for (const { label, games } of dayBuckets.values()) {
          const hasLockOnDay = games.some((g) => {
            const id = String(g.game_id);
            return locks[id] !== undefined ? locks[id] : Boolean(existingLocks[id]);
          });
          if (!hasLockOnDay) missingLockDays.push({ label });
        }
        missingLockDays.sort((a, b) => a.label.localeCompare(b.label));
      }

      const missingQuestions = [];
      for (const t of tbList) {
        const tid = String(t.tiebreaker_id);
        if (!tiebreakerIsAnswered(tid, tiebreakerPicks, existingTiebreakerPicks)) {
          missingQuestions.push({
            tid,
            question: t.question,
            deadline: formatDateForDisplay(t.start_time),
          });
        }
      }

      return { missingGames, missingLockDays, missingQuestions };
    },
    [picks, existingPicks, locks, existingLocks, tiebreakerPicks, existingTiebreakerPicks]
  );

  const runSubmitPicks = async () => {
    setIsSubmitting(true);
    setError(null);

    try {
      const gamesToSubmit = new Set([...Object.keys(picks), ...Object.keys(locks)]);

      const gamePickResponses = await Promise.all(
        Array.from(gamesToSubmit).map((gid) => {
          const pickedTeam = picks[gid] || existingPicks[gid];
          if (!pickedTeam) throw new Error(`No pick found for game ${gid}`);

          const hasLockChange = locks[gid] !== undefined;
          const isLocked = hasLockChange ? locks[gid] : (existingLocks[gid] || false);

          const data = { game_id: gid, picked_team: pickedTeam };
          if (hasLockChange) data.lock = isLocked;

          return api.post("/submit_pick", data);
        })
      );

      const tiebreakerPickResponses = await Promise.all(
        Object.entries(tiebreakerPicks).map(([tid, answer]) =>
          api.post("/tiebreaker_picks", { tiebreaker_id: tid, answer })
        )
      );

      const gameMessages = gamePickResponses.map((r) => r.data.message).filter(Boolean);
      const tbMessages = tiebreakerPickResponses.map((r) => r.data.message).filter(Boolean);

      let msg = "";
      if (gameMessages.length > 0) {
        const unique = [...new Set(gameMessages)];
        msg = unique.length === 1 ? unique[0] : `Updated ${gameMessages.length} picks successfully`;
      }
      if (tbMessages.length > 0) {
        if (msg) msg += "\n";
        const unique = [...new Set(tbMessages)];
        msg += unique.length === 1 ? unique[0] : `Updated ${tbMessages.length} tiebreakers successfully`;
      }

      setIsSubmitting(false);
      if (msg) alert(msg);
      setError(null);
      setExistingPicks({ ...existingPicks, ...picks });
      setExistingTiebreakerPicks({ ...existingTiebreakerPicks, ...tiebreakerPicks });
      setExistingLocks({ ...existingLocks, ...locks });
      setPicks({});
      setTiebreakerPicks({});
      setLocks({});
    } catch (err) {
      if (!handleAuthError(err)) {
        if (err.response && err.response.status === 403) {
          setError("You do not have permission to make picks. Please contact an administrator.");
        } else if (err.response?.data?.detail) {
          const detail = err.response.data.detail;
          if (
            detail.includes("Cannot change lock") ||
            detail.includes("Your Locked game") ||
            detail.includes("Cannot unlock") ||
            detail.includes("Your lock cannot be changed")
          ) {
            setError(detail);
            setLocks({});
          } else {
            setError(`Error: ${detail}`);
          }
        } else if (err.message) {
          setError(`Error: ${err.message}`);
        } else {
          setError("Failed to submit picks. Please try again.");
        }
      }
      setIsSubmitting(false);
    }
  };

  const availableGames = useMemo(() =>
    games.filter(g => g?.game_date && !picksFrozenForGame(g.game_date))
      .sort((a, b) => new Date(a.game_date) - new Date(b.game_date)),
    [games, picksFrozenForGame]
  );

  const availableTiebreakers = useMemo(() =>
    tiebreakers.filter(t => t?.start_time && tiebreakerPickStillOpen(t.start_time) && t.is_active)
      .sort((a, b) => new Date(a.start_time) - new Date(b.start_time)),
    [tiebreakers, tiebreakerPickStillOpen]
  );

  const onSubmitClick = () => {
    const games = availableGames;
    const tbs = availableTiebreakers;
    if (games.length === 0 && tbs.length === 0) {
      runSubmitPicks();
      return;
    }
    setIsCheckingWarnings(true);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const w = computeSubmitWarnings(games, tbs);
        setIsCheckingWarnings(false);
        const needsLockWarning = SHOW_LOCK_OF_THE_DAY_UI && w.missingLockDays.length > 0;
        if (
          w.missingGames.length > 0 ||
          needsLockWarning ||
          w.missingQuestions.length > 0
        ) {
          setSubmitWarnings(w);
          setShowSubmitWarning(true);
        } else {
          runSubmitPicks();
        }
      });
    });
  };

  const hasUnsavedChanges = useMemo(
    () =>
      Object.keys(picks).length > 0 ||
      Object.keys(locks).length > 0 ||
      Object.keys(tiebreakerPicks).length > 0,
    [picks, locks, tiebreakerPicks]
  );

  /* beforeunload only — useBlocker requires createBrowserRouter/RouterProvider, not BrowserRouter */
  useEffect(() => {
    if (!hasUnsavedChanges) return undefined;
    const onBeforeUnload = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [hasUnsavedChanges]);

  const confirmSubmitDespiteWarnings = () => {
    setShowSubmitWarning(false);
    runSubmitPicks();
  };

  return (
    <Container fluid="md" className="px-2 px-md-3">
      <Row className="mb-3 mb-md-4">
        <Col>
          <h2 className="text-center text-md-start">Make Your Picks</h2>
          <p className="text-muted text-center text-md-start">Select your picks for upcoming games and answer any tiebreaker questions. Game picks and tiebreaker answers lock 1 minute before the scheduled time.</p>
        </Col>
      </Row>

      {error && (
        <Row className="mb-3 mb-md-4"><Col><Alert variant="danger">{error}</Alert></Col></Row>
      )}

      {isLoading ? (
        <Row><Col className="text-center">
          <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '200px' }}>
            <div className="spinner-border text-primary" role="status"><span className="visually-hidden">Loading...</span></div>
            <span className="ms-3">Loading picks data...</span>
          </div>
        </Col></Row>
      ) : error ? null : (availableGames.length === 0 && availableTiebreakers.length === 0) ? (
        <Row><Col><Alert variant="info">No available contests to pick at this time</Alert></Col></Row>
      ) : (
        <>
          {availableGames.length > 0 && (
            <>
              <Row className="mb-3">
                <Col>
                  <h3 className="text-center text-md-start">Games</h3>
                  <p className="text-muted text-center text-md-start mb-0">
                    {SHOW_LOCK_OF_THE_DAY_UI ? (
                      <>
                        Click the lock icon on a game to set your lock of the day — if that pick wins, it scores double points. Note: The lock goes with the day the game is played, not with the day you make your picks.
                      </>
                    ) : (
                      <>Pick the team you think will cover the spread for each game.</>
                    )}
                  </p>
                </Col>
              </Row>
              <Row xs={1} sm={2} lg={3} className="g-3 g-md-4 mb-4">
                {availableGames.map(game => {
                  const gid = String(game.game_id);
                  const existingPick = existingPicks[gid];
                  const currentPick = picks[gid];
                  const selectedTeam = currentPick || existingPick;
                  const isLocked = SHOW_LOCK_OF_THE_DAY_UI && (locks[gid] !== undefined ? locks[gid] : (existingLocks[gid] || false));

                  return (
                    <Col key={`game-${game.game_id}`}>
                      <Card className={`h-100 shadow-sm ${isLocked ? 'border-warning border-3' : 'border-3'}`} style={isLocked ? {} : {borderColor: 'transparent'}}>
                        <Card.Body className="d-flex flex-column">
                          <Card.Title className={`d-flex ${SHOW_LOCK_OF_THE_DAY_UI ? 'justify-content-between' : ''} align-items-center mb-3`}>
                            <div className="d-flex align-items-center">
                              <span className="text-truncate me-1">{game.away_team}</span>
                              <small className="text-muted mx-1">@</small>
                              <span className="text-truncate ms-1">{game.home_team}</span>
                            </div>
                          </Card.Title>
                          <Card.Text className="mb-3">
                            <div className="mb-1"><strong>Spread:</strong> {game.spread > 0 ? `${game.home_team} -${game.spread}` : `${game.away_team} -${Math.abs(game.spread)}`}</div>
                            <div className="mb-1"><strong>Game time:</strong> {formatDateForDisplay(game.game_date)}</div>
                            {existingPick && (
                              <div className="mt-2 text-success">
                                <strong>Your pick: {existingPick}</strong>
                                {isLocked && <span className="ms-2 text-warning">Lock of the day</span>}
                              </div>
                            )}
                          </Card.Text>
                          <div className="d-grid gap-2 mt-auto">
                            <Button variant={selectedTeam === game.away_team ? "success" : "outline-primary"} onClick={() => handlePick(game.game_id, game.away_team)} className="py-2">
                              {game.away_team} {game.spread > 0 ? `+${game.spread}` : `-${Math.abs(game.spread)}`}
                            </Button>
                            <Button variant={selectedTeam === game.home_team ? "success" : "outline-primary"} onClick={() => handlePick(game.game_id, game.home_team)} className="py-2">
                              {game.home_team} {game.spread > 0 ? `-${game.spread}` : `+${Math.abs(game.spread)}`}
                            </Button>
                          </div>
                        </Card.Body>
                      </Card>
                    </Col>
                  );
                })}
              </Row>
            </>
          )}

          {availableTiebreakers.length > 0 && (
            <><br />
              <Row className="mb-3"><Col><h3 className="text-center text-md-start">Questions</h3></Col></Row>
              <Row xs={1} sm={2} lg={3} className="g-3 g-md-4">
                {availableTiebreakers.map(tiebreaker => {
                  const tid = String(tiebreaker.tiebreaker_id);
                  const existingAnswer = existingTiebreakerPicks[tid];
                  const currentAnswer = tiebreakerPicks[tid];
                  const answer = currentAnswer !== undefined ? currentAnswer : existingAnswer;
                  const q = tiebreaker.question.toLowerCase();
                  const looksLikeNumeric = q.includes('how many') || q.includes('score') || q.includes('points') || q.includes('total');
                  const asksForEntity = q.includes('which team') || q.includes('which player') || q.includes('who will') || q.includes('who wins') || q.includes('name the') || q.includes('what team');
                  const isNumeric = looksLikeNumeric && !asksForEntity;

                  return (
                    <Col key={`tiebreaker-${tiebreaker.tiebreaker_id}`}>
                      <Card className="h-100 shadow-sm">
                        <Card.Body className="d-flex flex-column">
                          <Card.Title className="mb-3">{tiebreaker.question}</Card.Title>
                          <Card.Text className="mb-3">
                            <div className="mb-1">
                              <strong>Scheduled start:</strong> {formatDateForDisplay(tiebreaker.start_time)}
                              <span className="text-muted"> (answers lock 1 minute before)</span>
                            </div>
                            {existingAnswer !== undefined && (
                              <div className="mt-2 text-success"><strong>Your answer: {existingAnswer}</strong></div>
                            )}
                          </Card.Text>
                          <Form.Group className="mt-auto">
                            <Form.Control
                              type={isNumeric ? "number" : "text"}
                              step={isNumeric ? "0.1" : undefined}
                              placeholder="Enter your answer"
                              value={answer !== undefined ? answer : ''}
                              onChange={(e) => handleTiebreakerPick(tiebreaker.tiebreaker_id, e.target.value, isNumeric)}
                              className="text-center"
                            />
                          </Form.Group>
                        </Card.Body>
                      </Card>
                    </Col>
                  );
                })}
              </Row>
            </>
          )}

          {(Object.keys(picks).length > 0 || Object.keys(tiebreakerPicks).length > 0 || Object.keys(locks).length > 0) && (
            <Row className="mt-4"><Col className="d-flex justify-content-center">
              <Button variant="success" size="lg" onClick={onSubmitClick} disabled={isSubmitting || isCheckingWarnings} className="px-4 py-2">Save Picks</Button>
            </Col></Row>
          )}
        </>
      )}

      <Modal show={showSubmitWarning} onHide={() => setShowSubmitWarning(false)} centered>
        <Modal.Header closeButton>
          <Modal.Title>Before you submit</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {(submitWarnings.missingGames.length > 0 ||
            (SHOW_LOCK_OF_THE_DAY_UI && submitWarnings.missingLockDays.length > 0) ||
            submitWarnings.missingQuestions.length > 0) && (
            <p className="text-muted small mb-3">
              You still have incomplete entries. You can go back to finish them, or save anyway — only games and answers you&apos;ve changed will be saved.
            </p>
          )}
          {submitWarnings.missingGames.length > 0 && (
            <>
              <h6 className="fw-bold">Games without a pick</h6>
              <ul className="small mb-3 ps-3">
                {submitWarnings.missingGames.map((g) => (
                  <li key={g.gid}>
                    <strong>{g.label}</strong>
                    <span className="text-muted"> — {g.time}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          {SHOW_LOCK_OF_THE_DAY_UI && submitWarnings.missingLockDays.length > 0 && (
            <>
              <h6 className="fw-bold">Game days without a lock of the day</h6>
              <ul className="small mb-3 ps-3">
                {submitWarnings.missingLockDays.map((d) => (
                  <li key={d.label}>{d.label}</li>
                ))}
              </ul>
            </>
          )}
          {submitWarnings.missingQuestions.length > 0 && (
            <>
              <h6 className="fw-bold">Questions without an answer</h6>
              <ul className="small mb-0 ps-3">
                {submitWarnings.missingQuestions.map((q) => (
                  <li key={q.tid}>
                    <strong className="d-block">{q.question}</strong>
                    <span className="text-muted">Scheduled: {q.deadline} (locks 1 min before)</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Modal.Body>
        <Modal.Footer className="d-flex flex-wrap gap-2 justify-content-between">
          <Button variant="outline-secondary" onClick={() => setShowSubmitWarning(false)}>
            Go back
          </Button>
          <Button variant="success" onClick={confirmSubmitDespiteWarnings}>
            Save anyway
          </Button>
        </Modal.Footer>
      </Modal>

      {isCheckingWarnings && (
        <div
          className="d-flex align-items-center justify-content-center"
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.5)",
            zIndex: 9998,
          }}
        >
          <div className="bg-white rounded-3 p-4 text-center shadow" style={{ minWidth: "280px" }}>
            <div className="mb-3 d-flex justify-content-center">
              <BasketballSpinnerIcon size={56} />
            </div>
            <h5 className="mb-2">Checking your picks…</h5>
            <p className="text-muted small mb-0">Hang on a moment.</p>
          </div>
        </div>
      )}

      {isSubmitting && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
          <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '0.5rem', textAlign: 'center', minWidth: '300px' }}>
            <div className="mb-3"><div className="spinner-border text-primary" style={{ width: '3rem', height: '3rem' }} role="status"><span className="visually-hidden">Loading...</span></div></div>
            <h5 className="mb-2">Saving your picks</h5>
            <p className="text-muted mb-0">Please wait…</p>
          </div>
        </div>
      )}
    </Container>
  );
}
