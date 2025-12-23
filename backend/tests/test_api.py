"""Integration tests for API endpoints.

These tests use mocked database sessions to test the API layer
without requiring a running database.
"""

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient


@pytest.fixture
def mock_db_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def app(mock_db_session):
    """Create test app with mocked database."""
    from src.api.main import app
    from src.api.deps import get_db_session

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db_session] = override_get_db
    yield app
    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /api/health endpoint."""

    def test_health_check_success(self, client, mock_db_session):
        """Test health check returns healthy status."""
        # Mock successful database query
        mock_db_session.execute.return_value = MagicMock()

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

    def test_health_check_db_failure(self, client, mock_db_session):
        """Test health check when database is down."""
        # Mock database failure
        mock_db_session.execute.side_effect = Exception("Connection refused")

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "disconnected"


class TestBrandsEndpoints:
    """Tests for /api/brands endpoints."""

    def test_list_brands_empty(self, client, mock_db_session):
        """Test listing brands when none exist."""
        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/brands")

        assert response.status_code == 200
        data = response.json()
        assert data["brands"] == []
        assert data["total"] == 0

    def test_list_brands_with_data(self, client, mock_db_session):
        """Test listing brands with data."""
        # Create mock brand
        mock_brand = MagicMock()
        mock_brand.id = uuid4()
        mock_brand.name = "Nike"
        mock_brand.milled_slug = "nike"
        mock_brand.is_active = True
        mock_brand.excluded_categories = []
        mock_brand.created_at = datetime.utcnow()
        mock_brand.updated_at = datetime.utcnow()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_brand]
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/brands")

        assert response.status_code == 200
        data = response.json()
        assert len(data["brands"]) == 1
        assert data["brands"][0]["name"] == "Nike"

    def test_create_brand_validation_error(self, client, mock_db_session):
        """Test creating brand with missing required fields."""
        response = client.post(
            "/api/brands",
            json={"name": "Test"},  # Missing milled_slug
        )

        assert response.status_code == 422  # Validation error

    def test_get_brand_not_found(self, client, mock_db_session):
        """Test getting non-existent brand."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.get(f"/api/brands/{uuid4()}")

        assert response.status_code == 404


class TestPredictionsEndpoints:
    """Tests for /api/predictions endpoints."""

    def test_list_predictions_empty(self, client, mock_db_session):
        """Test listing predictions when none exist."""
        # Mock for count query
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        # Mock for data query
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [count_result, data_result]

        response = client.get("/api/predictions")

        assert response.status_code == 200
        data = response.json()
        assert data["predictions"] == []
        assert data["total"] == 0

    def test_list_upcoming_predictions(self, client, mock_db_session):
        """Test listing upcoming predictions."""
        # Create mock prediction
        mock_brand = MagicMock()
        mock_brand.id = uuid4()
        mock_brand.name = "Nike"

        mock_prediction = MagicMock()
        mock_prediction.id = uuid4()
        mock_prediction.brand_id = mock_brand.id
        mock_prediction.brand = mock_brand
        mock_prediction.source_window_id = uuid4()
        mock_prediction.source_window = None
        mock_prediction.predicted_start = date(2024, 12, 25)
        mock_prediction.predicted_end = date(2024, 12, 31)
        mock_prediction.discount_summary = "30% off"
        mock_prediction.milled_reference_url = None
        mock_prediction.confidence = 0.75
        mock_prediction.calendar_event_id = None
        mock_prediction.notified_at = None
        mock_prediction.outcome = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_prediction]
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/predictions/upcoming?days=30")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_get_prediction_not_found(self, client, mock_db_session):
        """Test getting non-existent prediction."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.get(f"/api/predictions/{uuid4()}")

        assert response.status_code == 404


class TestReviewEndpoints:
    """Tests for /api/review endpoints."""

    def test_list_reviews_empty(self, client, mock_db_session):
        """Test listing reviews when none pending."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/review")

        assert response.status_code == 200
        data = response.json()
        assert data["reviews"] == []
        assert data["total"] == 0

    def test_approve_review_not_found(self, client, mock_db_session):
        """Test approving non-existent review."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.post(f"/api/review/{uuid4()}/approve")

        assert response.status_code == 404

    def test_reject_review_not_found(self, client, mock_db_session):
        """Test rejecting non-existent review."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.post(f"/api/review/{uuid4()}/reject")

        assert response.status_code == 404


class TestAccuracyEndpoints:
    """Tests for /api/accuracy endpoints."""

    def test_get_overall_accuracy_empty(self, client, mock_db_session):
        """Test overall accuracy with no data."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/accuracy")

        assert response.status_code == 200
        data = response.json()
        assert data["total_predictions"] == 0
        assert data["hit_rate"] == 0

    def test_get_brand_accuracy_not_found(self, client, mock_db_session):
        """Test getting accuracy for non-existent brand."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.get(f"/api/accuracy/brands/{uuid4()}")

        assert response.status_code == 404

    def test_list_suggestions_empty(self, client, mock_db_session):
        """Test listing suggestions when none exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/accuracy/suggestions")

        assert response.status_code == 200
        data = response.json()
        assert data["suggestions"] == []
        assert data["total"] == 0

    def test_approve_suggestion_not_found(self, client, mock_db_session):
        """Test approving non-existent suggestion."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.post(f"/api/accuracy/suggestions/{uuid4()}/approve")

        assert response.status_code == 404

    def test_dismiss_suggestion_not_found(self, client, mock_db_session):
        """Test dismissing non-existent suggestion."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.post(f"/api/accuracy/suggestions/{uuid4()}/dismiss")

        assert response.status_code == 404

    def test_recalculate_accuracy(self, client, mock_db_session):
        """Test accuracy recalculation endpoint."""
        # Mock empty brands
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.post("/api/accuracy/recalculate")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
