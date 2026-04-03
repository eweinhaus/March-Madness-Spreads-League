import React, { useState, useEffect } from 'react';
import { Container, Form, Button, Table, Alert, Modal } from 'react-bootstrap';
import api from '../api';

const AdminGames = () => {
  const [games, setGames] = useState([]);
  const [newGame, setNewGame] = useState({
    home_team: '',
    away_team: '',
    spread: '',
    game_date: '',
  });
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [editingGame, setEditingGame] = useState(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [gameToDelete, setGameToDelete] = useState(null);

  useEffect(() => {
    fetchGames();
  }, []);

  const fetchGames = async () => {
    try {
      const response = await api.get('/games', {
        headers: {
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        },
        params: {
          all_games: true,
          _t: Date.now()
        }
      });
      setGames(response.data);
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Please log in to access this page.');
      } else if (err.response?.status === 403) {
        setError('You do not have permission to access this page.');
      } else {
        setError('Failed to fetch games. Try logging out and logging back in.');
      }
      console.error('Error fetching games:', err);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setNewGame(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const toUtcISOStringFromLocal = (localDateTime) => {
    if (!localDateTime) return '';
    const [datePart, timePartRaw] = localDateTime.split('T');
    const [year, month, day] = datePart.split('-').map(Number);
    const [hour, minute] = (timePartRaw || '00:00').split(':').map(Number);
    const localDate = new Date(year, (month || 1) - 1, day || 1, hour || 0, minute || 0, 0, 0);
    return localDate.toISOString();
  };

  const formatDateForDisplay = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  const hasGameStarted = (dateString) => {
    const now = new Date();
    const gameTime = new Date(dateString);
    return now.getTime() >= gameTime.getTime();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    
    try {
      const utcDateString = toUtcISOStringFromLocal(newGame.game_date);
      
      const gameData = {
        ...newGame,
        spread: parseFloat(newGame.spread),
        game_date: utcDateString,
      };
      
      await api.post('/games', gameData);
      
      await fetchGames();
      setNewGame({
        home_team: '',
        away_team: '',
        spread: '',
        game_date: '',
      });
      
      setSuccess('Game added successfully!');
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Please log in to add games.');
      } else if (err.response?.status === 403) {
        setError('You do not have permission to add games.');
      } else if (err.response?.status === 400) {
        const errorMessage = err.response?.data?.detail || 'Validation error occurred';
        setError(`Validation Error: ${errorMessage}`);
      } else {
        setError(`Failed to add game: ${err.response?.data?.detail || err.message}`);
      }
      console.error('Error adding game:', err);
    }
  };

  const handleWinnerSelect = async (gameId, winningTeam) => {
    setError(null);
    setSuccess(null);
    
    try {
      await api.post('/update_score', {
        game_id: gameId,
        winning_team: winningTeam
      });
      
      await fetchGames();
      setSuccess('Game result updated successfully!');
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Please log in to update game results.');
      } else if (err.response?.status === 403) {
        setError('You do not have permission to update game results.');
      } else {
        setError('Failed to update game result. Please try again.');
      }
      console.error('Error updating game result:', err);
    }
  };

  const handleEditClick = (game) => {
    const utcDate = new Date(game.game_date);
    
    const localYear = utcDate.getFullYear();
    const localMonth = String(utcDate.getMonth() + 1).padStart(2, '0');
    const localDay = String(utcDate.getDate()).padStart(2, '0');
    const localHours = String(utcDate.getHours()).padStart(2, '0');
    const localMinutes = String(utcDate.getMinutes()).padStart(2, '0');
    
    const localDateString = `${localYear}-${localMonth}-${localDay}T${localHours}:${localMinutes}`;
    
    setEditingGame({
      ...game,
      game_date: localDateString
    });
    setShowEditModal(true);
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    
    try {
      const utcDateString = toUtcISOStringFromLocal(editingGame.game_date);
      
      const gameData = {
        ...editingGame,
        spread: parseFloat(editingGame.spread),
        game_date: utcDateString,
      };
      
      await api.put(`/games/${editingGame.id}`, gameData);
      
      await fetchGames();
      setShowEditModal(false);
      setSuccess('Game updated successfully!');
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Please log in to edit games.');
      } else if (err.response?.status === 403) {
        setError('You do not have permission to edit games.');
      } else {
        setError('Failed to update game. Please try again.');
      }
      console.error('Error updating game:', err);
    }
  };

  const handleEditInputChange = (e) => {
    const { name, value } = e.target;
    setEditingGame(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleDeleteClick = (game) => {
    setGameToDelete(game);
    setShowDeleteConfirm(true);
  };

  const handleDeleteConfirm = async () => {
    setError(null);
    setSuccess(null);
    
    try {
      await api.delete(`/games/${gameToDelete.id}`);
      
      await fetchGames();
      setShowDeleteConfirm(false);
      setSuccess('Game deleted successfully!');
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Please log in to delete games.');
      } else if (err.response?.status === 403) {
        setError('You do not have permission to delete games.');
      } else {
        setError('Failed to delete game. Please try again.');
      }
      console.error('Error deleting game:', err);
    }
  };

  return (
    <Container className="py-4">
      <h2 className="mb-4">Manage Games</h2>
      
      {error && <Alert variant="danger">{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {/* Add Game Form */}
      <Form onSubmit={handleSubmit} className="mb-5" style={{ maxWidth: '400px' }}>
        <Form.Group className="mb-3">
          <Form.Label>Away Team</Form.Label>
          <Form.Control
            type="text"
            name="away_team"
            value={newGame.away_team}
            onChange={handleInputChange}
            required
          />
        </Form.Group>

        <Form.Group className="mb-3">
          <Form.Label>Home Team</Form.Label>
          <Form.Control
            type="text"
            name="home_team"
            value={newGame.home_team}
            onChange={handleInputChange}
            required
          />
        </Form.Group>

        <Form.Group className="mb-3">
          <Form.Label>Spread (positive for home team favorite)</Form.Label>
          <Form.Control
            type="number"
            step="0.5"
            name="spread"
            value={newGame.spread}
            onChange={handleInputChange}
            required
          />
        </Form.Group>

        <Form.Group className="mb-3">
          <Form.Label>Game Date & Time (Your Local Time)</Form.Label>
          <Form.Control
            type="datetime-local"
            name="game_date"
            value={newGame.game_date}
            onChange={handleInputChange}
            required
            step="300"
          />
        </Form.Group>

        <Button variant="primary" type="submit">
          Add Game
        </Button>
      </Form>

      {/* Games List */}
      <h3>All Games</h3>
      <Table striped bordered hover size="sm">
        <thead>
          <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
            <th className="py-2">Date</th>
            <th className="py-2">Matchup</th>
            <th className="py-2">Status</th>
            <th className="py-2">Actions</th>
          </tr>
        </thead>
        <tbody className="small">
          {games
            .sort((a, b) => new Date(b.game_date) - new Date(a.game_date))
            .map(game => {
            const gameStarted = hasGameStarted(game.game_date);
            return (
              <tr key={game.id} style={{ fontSize: '0.85rem', lineHeight: '1.2' }}>
                <td className="py-2">{formatDateForDisplay(game.game_date)}</td>
                <td className="py-2 text-nowrap">
                  {game.spread < 0 
                    ? `${game.away_team} @ ${game.home_team} +${Math.abs(game.spread)}` 
                    : `${game.away_team} @ ${game.home_team} -${game.spread}`}
                </td>
                <td className="py-2">
                  {game.winning_team ? (
                    <span className="text-success" style={{ fontSize: '0.85rem' }}>
                      {game.winning_team === "PUSH" ? "PUSH" : `Covered: ${game.winning_team}`}
                    </span>
                  ) : gameStarted ? (
                    <span className="text-warning" style={{ fontSize: '0.85rem' }}>Game in progress</span>
                  ) : (
                    <span className="text-info" style={{ fontSize: '0.85rem' }}>Not started</span>
                  )}
                </td>
                <td className="py-2">
                  <div className="d-flex gap-1">
                    {gameStarted && !game.winning_team && (
                      <div className="btn-group" role="group">
                        <Button
                          variant="outline-success"
                          size="sm"
                          className="py-0 px-2"
                          style={{ fontSize: '0.75rem' }}
                          onClick={() => handleWinnerSelect(game.id, game.away_team)}
                        >
                          {game.away_team} Covered
                        </Button>
                        <Button
                          variant="outline-warning"
                          size="sm"
                          className="py-0 px-2"
                          style={{ fontSize: '0.75rem' }}
                          onClick={() => handleWinnerSelect(game.id, "PUSH")}
                        >
                          Push
                        </Button>
                        <Button
                          variant="outline-success"
                          size="sm"
                          className="py-0 px-2"
                          style={{ fontSize: '0.75rem' }}
                          onClick={() => handleWinnerSelect(game.id, game.home_team)}
                        >
                          {game.home_team} Covered
                        </Button>
                      </div>
                    )}
                    <Button
                      variant="outline-primary"
                      size="sm"
                      className="py-0 px-2"
                      style={{ fontSize: '0.75rem' }}
                      onClick={() => handleEditClick(game)}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="outline-danger"
                      size="sm"
                      className="py-0 px-2"
                      style={{ fontSize: '0.75rem' }}
                      onClick={() => handleDeleteClick(game)}
                    >
                      Delete
                    </Button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </Table>

      {/* Edit Game Modal */}
      <Modal show={showEditModal} onHide={() => setShowEditModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Edit Game</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form onSubmit={handleEditSubmit}>
            <Form.Group className="mb-3">
              <Form.Label>Away Team</Form.Label>
              <Form.Control
                type="text"
                name="away_team"
                value={editingGame?.away_team || ''}
                onChange={handleEditInputChange}
                required
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Home Team</Form.Label>
              <Form.Control
                type="text"
                name="home_team"
                value={editingGame?.home_team || ''}
                onChange={handleEditInputChange}
                required
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Spread (positive for home team favorite)</Form.Label>
              <Form.Control
                type="number"
                step="0.5"
                name="spread"
                value={editingGame?.spread || ''}
                onChange={handleEditInputChange}
                required
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Game Date & Time</Form.Label>
              <Form.Control
                type="datetime-local"
                name="game_date"
                value={editingGame?.game_date || ''}
                onChange={handleEditInputChange}
                required
                step="300"
              />
            </Form.Group>

            {editingGame?.winning_team && (
              <Form.Group className="mb-3">
                <Form.Label>Result</Form.Label>
                <Form.Select
                  name="winning_team"
                  value={editingGame.winning_team}
                  onChange={handleEditInputChange}
                >
                  <option value="">No Result</option>
                  <option value={editingGame.away_team}>{editingGame.away_team} Covered</option>
                  <option value={editingGame.home_team}>{editingGame.home_team} Covered</option>
                  <option value="PUSH">Push</option>
                </Form.Select>
              </Form.Group>
            )}

            <div className="d-flex justify-content-end gap-2">
              <Button variant="secondary" onClick={() => setShowEditModal(false)}>
                Cancel
              </Button>
              <Button variant="primary" type="submit">
                Save Changes
              </Button>
            </div>
          </Form>
        </Modal.Body>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal show={showDeleteConfirm} onHide={() => setShowDeleteConfirm(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Confirm Delete</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          Are you sure you want to delete the game {gameToDelete?.away_team} @ {gameToDelete?.home_team}?
          This will also delete all picks associated with this game.
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowDeleteConfirm(false)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleDeleteConfirm}>
            Delete Game
          </Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
};

export default AdminGames;
