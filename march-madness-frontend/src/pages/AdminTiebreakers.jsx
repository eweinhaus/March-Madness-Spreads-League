import React, { useState, useEffect } from 'react';
import { Container, Form, Button, Table, Alert, Modal } from 'react-bootstrap';
import axios from 'axios';
import { API_URL } from "../config";

const AdminTiebreakers = () => {
  const [tiebreakers, setTiebreakers] = useState([]);
  const [newTiebreaker, setNewTiebreaker] = useState({
    question: '',
    start_time: '',
  });
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [editingTiebreaker, setEditingTiebreaker] = useState(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [tiebreakerToDelete, setTiebreakerToDelete] = useState(null);
  const [showFinishModal, setShowFinishModal] = useState(false);
  const [tiebreakerToFinish, setTiebreakerToFinish] = useState(null);
  const [finishScore, setFinishScore] = useState('');

  // Fetch tiebreakers on component mount
  useEffect(() => {
    fetchTiebreakers();
  }, []);

  const getAuthHeaders = () => {
    const token = localStorage.getItem('token');
    return {
      'Authorization': `Bearer ${token}`
    };
  };

  const fetchTiebreakers = async () => {
    try {
      const response = await axios.get(`${API_URL}/tiebreakers?is_active=true`, {
        headers: getAuthHeaders()
      });
      setTiebreakers(response.data);
    } catch (err) {
      setError('Failed to fetch tiebreakers. Please try again.');
      console.error('Error fetching tiebreakers:', err);
    }
  };

  const handleTiebreakerInputChange = (e) => {
    const { name, value } = e.target;
    setNewTiebreaker(prev => ({
      ...prev,
      [name]: value
    }));
  };

  // Helper function to format date for display
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

  const handleTiebreakerSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    
    try {
      // The datetime-local input is in the user's local timezone
      // We need to convert it to UTC for storage
      const localDate = new Date(newTiebreaker.start_time);
      
      // The toISOString() method automatically converts to UTC
      // This is the correct way to convert local time to UTC
      const utcDateString = localDate.toISOString();
      
      const tiebreakerData = {
        ...newTiebreaker,
        start_time: utcDateString,
      };

      const response = await axios.post(`${API_URL}/tiebreakers`, tiebreakerData, {
        headers: getAuthHeaders()
      });
      
      await fetchTiebreakers();
      setNewTiebreaker({
        question: '',
        start_time: '',
      });
      
      setSuccess('Tiebreaker added successfully!');
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Please log in to add tiebreakers.');
      } else if (err.response?.status === 403) {
        setError('You do not have permission to add tiebreakers.');
      } else {
        setError('Failed to add tiebreaker. Please try again.');
      }
      console.error('Error adding tiebreaker:', err);
    }
  };

  const handleEditClick = (tiebreaker) => {
    // Convert UTC start_time to local time for datetime-local input
    const utcDate = new Date(tiebreaker.start_time);
    
    // Create a new Date object in local timezone
    const localDate = new Date(utcDate.getTime() - (utcDate.getTimezoneOffset() * 60000));
    
    // Format as YYYY-MM-DDTHH:MM for datetime-local input
    const localDateString = localDate.toISOString().slice(0, 16);
    
    setEditingTiebreaker({
      ...tiebreaker,
      start_time: localDateString
    });
    setShowEditModal(true);
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    
    try {
      // Convert local time back to UTC for storage
      const localDate = new Date(editingTiebreaker.start_time);
      const utcDateString = localDate.toISOString();
      
      const tiebreakerData = {
        ...editingTiebreaker,
        start_time: utcDateString,
      };
      
      await axios.put(`${API_URL}/tiebreakers/${editingTiebreaker.id}`, tiebreakerData, {
        headers: getAuthHeaders()
      });
      
      await fetchTiebreakers();
      setShowEditModal(false);
      setSuccess('Tiebreaker updated successfully!');
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Please log in to edit tiebreakers.');
      } else if (err.response?.status === 403) {
        setError('You do not have permission to edit tiebreakers.');
      } else {
        setError('Failed to update tiebreaker. Please try again.');
      }
      console.error('Error updating tiebreaker:', err);
    }
  };

  const handleEditInputChange = (e) => {
    const { name, value } = e.target;
    setEditingTiebreaker(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleDeleteClick = (tiebreaker) => {
    setTiebreakerToDelete(tiebreaker);
    setShowDeleteConfirm(true);
  };

  const handleDeleteConfirm = async () => {
    setError(null);
    setSuccess(null);
    
    try {
      await axios.delete(`${API_URL}/tiebreakers/${tiebreakerToDelete.id}`, {
        headers: getAuthHeaders()
      });
      
      await fetchTiebreakers();
      setShowDeleteConfirm(false);
      setSuccess('Tiebreaker deleted successfully!');
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Please log in to delete tiebreakers.');
      } else if (err.response?.status === 403) {
        setError('You do not have permission to delete tiebreakers.');
      } else {
        setError('Failed to delete tiebreaker. Please try again.');
      }
      console.error('Error deleting tiebreaker:', err);
    }
  };

  const handleFinishClick = (tiebreaker) => {
    console.log('Starting finish process for tiebreaker:', tiebreaker);
    setTiebreakerToFinish(tiebreaker);
    setFinishScore('');
    setShowFinishModal(true);
  };

  const handleFinishSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    
    try {
      console.log('Preparing to finish tiebreaker:', tiebreakerToFinish);
      console.log('Finish answer entered:', finishScore);
      
      const finishData = {
        question: tiebreakerToFinish.question,
        start_time: tiebreakerToFinish.start_time,
        answer: finishScore,
        is_active: false
      };
      
      console.log('Sending finish data to API:', finishData);
      console.log('API endpoint:', `${API_URL}/tiebreakers/${tiebreakerToFinish.id}`);
      
      const response = await axios.put(`${API_URL}/tiebreakers/${tiebreakerToFinish.id}`, finishData, {
        headers: getAuthHeaders()
      });
      
      console.log('API response:', response.data);
      
      await fetchTiebreakers();
      setShowFinishModal(false);
      setSuccess('Tiebreaker finished successfully!');
    } catch (err) {
      console.error('Detailed error information:', {
        message: err.message,
        response: err.response?.data,
        status: err.response?.status,
        headers: err.response?.headers
      });
      
      if (err.response?.status === 401) {
        setError('Please log in to finish tiebreakers.');
      } else if (err.response?.status === 403) {
        setError('You do not have permission to finish tiebreakers.');
      } else {
        setError('Failed to finish tiebreaker. Please try again.');
      }
    }
  };

  return (
    <Container className="py-4">
      <h2 className="mb-4">Manage Questions</h2>
      
      {error && <Alert variant="danger">{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {/* Add Tiebreaker Form */}
      <Form onSubmit={handleTiebreakerSubmit} className="mb-5" style={{ maxWidth: '400px' }}>
        <Form.Group className="mb-3">
          <Form.Label>Question</Form.Label>
          <Form.Control
            type="text"
            name="question"
            value={newTiebreaker.question}
            onChange={handleTiebreakerInputChange}
            required
          />
        </Form.Group>

        <Form.Group className="mb-3">
          <Form.Label>Start Time</Form.Label>
          <Form.Control
            type="datetime-local"
            name="start_time"
            value={newTiebreaker.start_time}
            onChange={handleTiebreakerInputChange}
            required
            step="300"
          />
        </Form.Group>

        <Button variant="primary" type="submit">
          Add Tiebreaker
        </Button>
      </Form>

      {/* Tiebreakers List */}
      <h3>All Questions</h3>
      <Table striped bordered hover size="sm">
        <thead>
          <tr className="text-nowrap" style={{ fontSize: '0.9rem', lineHeight: '1.3' }}>
            <th className="py-2">Start Time</th>
            <th className="py-2">Question</th>
            <th className="py-2">Status</th>
            <th className="py-2">Answer</th>
            <th className="py-2">Actions</th>
          </tr>
        </thead>
        <tbody className="small">
          {tiebreakers
            .sort((a, b) => new Date(b.start_time) - new Date(a.start_time))
            .map(tiebreaker => (
            <tr key={tiebreaker.id} style={{ fontSize: '0.85rem', lineHeight: '1.2' }}>
              <td className="py-2">{formatDateForDisplay(tiebreaker.start_time)}</td>
              <td className="py-2">{tiebreaker.question}</td>
              <td className="py-2">
                <span className={`text-${tiebreaker.is_active ? 'info' : 'success'}`} style={{ fontSize: '0.85rem' }}>
                  {tiebreaker.is_active ? 'Active' : 'Inactive'}
                </span>
              </td>
              <td className="py-2">{tiebreaker.answer !== null ? tiebreaker.answer : '-'}</td>
              <td className="py-2">
                <div className="d-flex gap-1">
                  {tiebreaker.is_active && (
                    <Button
                      variant="outline-success"
                      size="sm"
                      className="py-0 px-2"
                      style={{ fontSize: '0.75rem' }}
                      onClick={() => handleFinishClick(tiebreaker)}
                    >
                      Finish
                    </Button>
                  )}
                  <Button
                    variant="outline-primary"
                    size="sm"
                    className="py-0 px-2"
                    style={{ fontSize: '0.75rem' }}
                    onClick={() => handleEditClick(tiebreaker)}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="outline-danger"
                    size="sm"
                    className="py-0 px-2"
                    style={{ fontSize: '0.75rem' }}
                    onClick={() => handleDeleteClick(tiebreaker)}
                  >
                    Delete
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>

      {/* Edit Tiebreaker Modal */}
      <Modal show={showEditModal} onHide={() => setShowEditModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Edit Tiebreaker</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form onSubmit={handleEditSubmit}>
            <Form.Group className="mb-3">
              <Form.Label>Question</Form.Label>
              <Form.Control
                type="text"
                name="question"
                value={editingTiebreaker?.question || ''}
                onChange={handleEditInputChange}
                required
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Start Time (Question locks at this time)</Form.Label>
              <Form.Control
                type="datetime-local"
                name="start_time"
                value={editingTiebreaker?.start_time || ''}
                onChange={handleEditInputChange}
                required
                step="300"
              />
            </Form.Group>

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
          Are you sure you want to delete this tiebreaker?
          This will also delete all user entries associated with this tiebreaker.
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowDeleteConfirm(false)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleDeleteConfirm}>
            Delete Tiebreaker
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Finish Tiebreaker Modal */}
      <Modal show={showFinishModal} onHide={() => setShowFinishModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Finish Tiebreaker</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form onSubmit={handleFinishSubmit}>
            <Form.Group className="mb-3">
              <Form.Label>Enter Result (or N/A if multiple results)</Form.Label>
                <Form.Control
                  type="text"
                  value={finishScore}
                  onChange={(e) => setFinishScore(e.target.value)}
                  required
                />
            </Form.Group>
            <div className="d-flex justify-content-end gap-2">
              <Button variant="secondary" onClick={() => setShowFinishModal(false)}>
                Cancel
              </Button>
              <Button variant="success" type="submit">
                Finish Tiebreaker
              </Button>
            </div>
          </Form>
        </Modal.Body>
      </Modal>
    </Container>
  );
};

export default AdminTiebreakers; 