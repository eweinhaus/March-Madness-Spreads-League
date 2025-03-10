import { Link } from "react-router-dom";
import { Container, Row, Col, Button } from "react-bootstrap";

export default function Home() {
  return (
    <div>
      <div className="bg-primary text-white py-5 mb-5">
        <Container>
          <Row className="align-items-center">
            <Col md={8} className="text-start">
              <h1 className="display-4 fw-bold mb-4">Welcome to March Madness Spreads!</h1>
              <p className="lead mb-4">
                Make your picks against the spread for March Madness games 
                and compete with others to see who can predict the most teams that cover.
              </p>
              <div className="d-flex gap-3">
                <Link to="/picks" className="btn btn-light btn-lg">Make Your Picks</Link>
                <Link to="/leaderboard" className="btn btn-outline-light btn-lg">View Leaderboard</Link>
              </div>
            </Col>
            <Col md={4} className="d-none d-md-block">
              {/* You could add an image or illustration here */}
            </Col>
          </Row>
        </Container>
      </div>

      <Container>
        <Row className="mb-5">
          <Col md={4}>
            <h3 className="mb-3">How to Play</h3>
            <p>Pick teams to cover the spread for each game. Get one point for each correct pick.</p>
          </Col>
          <Col md={4}>
            <h3 className="mb-3">Stay Updated</h3>
            <p>Check the leaderboard regularly to see how you stack up against other players.</p>
          </Col>
          <Col md={4}>
            <h3 className="mb-3">Win Prizes</h3>
            <p>Compete for glory and bragging rights as you climb the leaderboard!</p>
          </Col>
        </Row>
      </Container>
    </div>
  );
}
