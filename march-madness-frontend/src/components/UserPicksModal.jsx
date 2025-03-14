import React from 'react';
import { Modal, Table, Badge, Tabs, Tab } from 'react-bootstrap';
import { format } from 'date-fns';

const UserPicksModal = ({ show, onHide, userPicks }) => {
  if (!userPicks) return null;

  const { user, game_picks, tiebreaker_picks } = userPicks;

  const formatDate = (dateString) => {
    return format(new Date(dateString), 'MMM d, yyyy h:mm a');
  };

  const getStatusBadge = (pick, game) => {
    if (!pick) {
      return <Badge bg="warning">No Pick</Badge>;
    }
    if (!game.winning_team) {
      return <Badge bg="info">Pending</Badge>;
    }
    if (game.winning_team === "PUSH") {
      return <Badge bg="secondary">Push</Badge>;
    }
    return pick.points_awarded > 0 ? 
      <Badge bg="success">Won</Badge> : 
      <Badge bg="danger">Lost</Badge>;
  };

  return (
    <Modal show={show} onHide={onHide} size="lg">
      <Modal.Header closeButton>
        <Modal.Title>Picks for {user?.full_name}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Tabs defaultActiveKey="games" className="mb-3">
          <Tab eventKey="games" title="Game Picks">
            <Table striped bordered hover responsive>
              <thead>
                <tr>
                  <th>Game Date</th>
                  <th>Matchup</th>
                  <th>Spread</th>
                  <th>Pick</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {game_picks?.map((game) => (
                  <tr key={game.game_id}>
                    <td>{formatDate(game.game_date)}</td>
                    <td>{game.away_team} @ {game.home_team}</td>
                    <td>{game.spread}</td>
                    <td>
                      {game.picked_team || <span className="text-muted">-</span>}
                    </td>
                    <td>
                      {getStatusBadge(game.picked_team, game)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Tab>
          <Tab eventKey="tiebreakers" title="Tiebreaker Picks">
            <Table striped bordered hover responsive>
              <thead>
                <tr>
                  <th>Start Time</th>
                  <th>Question</th>
                  <th>Answer</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {tiebreaker_picks?.map((tiebreaker) => (
                  <tr key={tiebreaker.tiebreaker_id}>
                    <td>{formatDate(tiebreaker.start_time)}</td>
                    <td>{tiebreaker.question}</td>
                    <td>
                      {tiebreaker.user_answer || <span className="text-muted">-</span>}
                      {tiebreaker.correct_answer && (
                        <span className="text-muted ms-2">
                          (Correct: {tiebreaker.correct_answer})
                        </span>
                      )}
                    </td>
                    <td>
                      {!tiebreaker.user_answer ? (
                        <Badge bg="warning">No Answer</Badge>
                      ) : !tiebreaker.correct_answer ? (
                        <Badge bg="info">Pending</Badge>
                      ) : tiebreaker.points_awarded > 0 ? (
                        <Badge bg="success">Won</Badge>
                      ) : (
                        <Badge bg="danger">Lost</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Tab>
        </Tabs>
      </Modal.Body>
    </Modal>
  );
};

export default UserPicksModal; 