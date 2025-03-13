import React, { useState, useEffect } from 'react';
import { Container, Form, Button, Table, Alert, Modal } from 'react-bootstrap';
import axios from 'axios';
import { API_URL } from "../config";

const AdminGames = () => {
  const [games, setGames] = useState([]);
  const [newGame, setNewGame] = useState({
    home_team: '',
    away_team: '',
    spread: '',
    game_date: '',
    half: 1
  });
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [editingGame, setEditingGame] = useState(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [gameToDelete, setGameToDelete] = useState(null);

  // Fetch games on component mount
  useEffect(() => {
    console.log('User Local Time:', new Date().toLocaleString());
    console.log('User Timezone:', Intl.DateTimeFormat().resolvedOptions().timeZone);
    fetchGames();
  }, []);

  const getAuthHeaders = () => {
    const token = localStorage.getItem('token');
    return {
      'Authorization': `Bearer ${token}`
    };
  };

  const fetchGames = async () => {
    try {
      const response = await axios.get(`${API_URL}/games`, {
        headers: getAuthHeaders()
      });
      setGames(response.data);
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Please log in to access this page.');
      } else if (err.response?.status === 403) {
        setError('You do not have permission to access this page.');
      } else {
        setError('Failed to fetch games. Please try again.');
      }
      console.error('Error fetching games:', err);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setNewGame(prev => ({
      ...prev,
      [name]: name === 'half' ? parseInt(value) : value
    }));
  };

  // Convert local time to UTC for database storage
  const localToUTC = (localDateString) => {
    //This function is not needed because the datetime-local input already stores the time in UTC
    //Get local time
    const local = new Date(localDateString);
    return local.toISOString();
  };

  // Convert UTC from database to local time (EDT)
  const utcToLocal = (utcDateString) => {
    //Get time in utc
    const utc = new Date(utcDateString);
    //Get offset from utc
    const offset = utc.getTimezoneOffset();
    //Convert to local time
    const local = new Date(utc.getTime() - (offset * 60 * 1000));
    return local;
  };

  // Helper function to format date for datetime-local input
  const formatDateForInput = (utcDateString) => {
    const localDate = utcToLocal(utcDateString);
    
    // Format in local time
    const year = localDate.getFullYear();
    const month = String(localDate.getMonth() + 1).padStart(2, '0');
    const day = String(localDate.getDate()).padStart(2, '0');
    const hours = String(localDate.getHours()).padStart(2, '0');
    const minutes = String(localDate.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  };

  // Helper function to format date for display
  const formatDateForDisplay = (utcDateString) => {
    const localDate = utcToLocal(utcDateString);
    
    // Format in local time with timezone name
    return localDate.toLocaleString('en-US', {
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
      timeZoneName: 'short'  // This will show EDT/EST
    });
  };

  // Helper function to check if a game has started
  const hasGameStarted = (utcDateString) => {
    const now = new Date();  // Local time
    const gameTime = new Date(utcDateString);  // Converts UTC to local automatically
    return now >= gameTime;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    
    try {
      console.log('User Entered Time:', newGame.game_date);
      console.log('User Timezone:', Intl.DateTimeFormat().resolvedOptions().timeZone);
      
      const gameData = {
        ...newGame,
        spread: parseFloat(newGame.spread),
        game_date: localToUTC(newGame.game_date),
        half: parseInt(newGame.half)  // Ensure half is parsed as integer
      };
      
      const response = await axios.post(`${API_URL}/games`, gameData, {
        headers: getAuthHeaders()
      });
      
      await fetchGames();
      setNewGame({
        home_team: '',
        away_team: '',
        spread: '',
        game_date: '',
        half: 1
      });
      
      setSuccess('Game added successfully!');
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Please log in to add games.');
      } else if (err.response?.status === 403) {
        setError('You do not have permission to add games.');
      } else {
        setError('Failed to add game. Please try again.');
      }
      console.error('Error adding game:', err);
    }
  };

  const handleWinnerSelect = async (gameId, winningTeam) => {
    setError(null);
    setSuccess(null);
    
    try {
      await axios.post(`${API_URL}/update_score`, {
        game_id: gameId,
        winning_team: winningTeam
      }, {
        headers: getAuthHeaders()
      });
      
      // Refresh games list
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
    const localGameDate = formatDateForInput(game.game_date);  // Convert UTC to local for edit form
    setEditingGame({
      ...game,
      game_date: localGameDate
    });
    setShowEditModal(true);
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    
    try {
      const gameData = {
        ...editingGame,
        spread: parseFloat(editingGame.spread),
        game_date: localToUTC(editingGame.game_date),
        half: parseInt(editingGame.half)  // Ensure half is parsed as integer
      };
      
      await axios.put(`${API_URL}/games/${editingGame.id}`, gameData, {
        headers: getAuthHeaders()
      });
      
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
      [name]: name === 'half' ? parseInt(value) : value
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
      await axios.delete(`${API_URL}/games/${gameToDelete.id}`, {
        headers: getAuthHeaders()
      });
      
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
      <h2 className="mb-4">Admin: Manage Games</h2>
      
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

        <Form.Group className="mb-3">
          <Form.Label>Tournament Half</Form.Label>
          <Form.Select
            name="half"
            value={newGame.half}
            onChange={handleInputChange}
            required
          >
            <option value={1}>Start through 32</option>
            <option value={2}>16 through Finals</option>
          </Form.Select>
        </Form.Group>

        <Button variant="primary" type="submit">
          Add Game
        </Button>
      </Form>

      {/* Games List */}
      <h3>Current Games</h3>
      <Table striped bordered hover>
        <thead>
          <tr>
            <th>Date</th>
            <th>Matchup</th>
            <th>Spread</th>
            <th>Half</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {games.map(game => {
            const gameStarted = hasGameStarted(game.game_date);
            return (
              <tr key={game.id}>
                <td>{formatDateForDisplay(game.game_date)}</td>
                <td>{game.away_team} @ {game.home_team}</td>
                <td>{game.spread > 0 ? `${game.home_team} -${game.spread}` : `${game.away_team} +${-game.spread}`}</td>
                <td>{game.half === 1 ? 'Start through 32' : '16 through Finals'}</td>
                <td>
                  {game.winning_team ? (
                    <span className="text-success">
                      {game.winning_team === "PUSH" ? "PUSH" : `Covered: ${game.winning_team}`}
                    </span>
                  ) : gameStarted ? (
                    <span className="text-warning">Game in progress</span>
                  ) : (
                    <span className="text-info">Not started</span>
                  )}
                </td>
                <td>
                  <div className="d-flex gap-2">
                    {gameStarted && !game.winning_team && (
                      <div className="btn-group" role="group">
                        <Button
                          variant="outline-success"
                          size="sm"
                          onClick={() => handleWinnerSelect(game.id, game.away_team)}
                        >
                          {game.away_team} Covered
                        </Button>
                        <Button
                          variant="outline-warning"
                          size="sm"
                          onClick={() => handleWinnerSelect(game.id, "PUSH")}
                        >
                          Push
                        </Button>
                        <Button
                          variant="outline-success"
                          size="sm"
                          onClick={() => handleWinnerSelect(game.id, game.home_team)}
                        >
                          {game.home_team} Covered
                        </Button>
                      </div>
                    )}
                    <Button
                      variant="outline-primary"
                      size="sm"
                      onClick={() => handleEditClick(game)}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="outline-danger"
                      size="sm"
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

            <Form.Group className="mb-3">
              <Form.Label>Tournament Half</Form.Label>
              <Form.Select
                name="half"
                value={editingGame?.half || 1}
                onChange={handleEditInputChange}
                required
              >
                <option value={1}>Start through 32</option>
                <option value={2}>16 through Finals</option>
              </Form.Select>
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