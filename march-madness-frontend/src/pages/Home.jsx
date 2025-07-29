import { Link } from "react-router-dom";
import { Container, Row, Col, Button } from "react-bootstrap";

export default function Home() {
  return (
    <div>
      <div className="bg-primary text-white py-4 py-md-5 mb-4 mb-md-5">
        <Container>
          <Row className="align-items-center">
            <Col md={8} className="text-center text-md-start">
              <h1 className="display-4 fw-bold mb-3 mb-md-4">Welcome to Spreads!</h1>
              <p className="lead mb-3 mb-md-4">
                Make your picks against the spread for sports games 
                and compete with others to see who can predict the most teams that cover.
              </p>
              <div className="d-flex flex-column flex-sm-row gap-2 gap-sm-3 justify-content-center justify-content-md-start">
                <Link to="/picks" className="btn btn-light btn-lg w-100 w-sm-auto">Make Your Picks</Link>
                <Link to="/leaderboard" className="btn btn-outline-light btn-lg w-100 w-sm-auto">View Leaderboard</Link>
              </div>
            </Col>
            <Col md={4} className="d-none d-md-block">
              {/* You could add an image or illustration here */}
            </Col>
          </Row>
        </Container>
      </div>

      <Container>
        <Row className="mb-4 mb-md-5 g-4">
          <Col sm={12} md={4}>
            <div className="p-3 bg-light rounded h-100">
              <h3 className="mb-3">How to Play</h3>
              <p>Pick teams to cover the spread for each game. Get one point for each correct pick.</p>
            </div>
          </Col>
          <Col sm={12} md={4}>
            <div className="p-3 bg-light rounded h-100">
              <h3 className="mb-3">Stay Updated</h3>
              <p>Check the leaderboard regularly to see how you stack up against other players.</p>
            </div>
          </Col>
          <Col sm={12} md={4}>
            <div className="p-3 bg-light rounded h-100">
              <h3 className="mb-3">Win Prizes</h3>
              <p>Compete for glory and bragging rights as you climb the leaderboard!</p>
            </div>
          </Col>
        </Row>
      </Container>
    </div>
  );
}
