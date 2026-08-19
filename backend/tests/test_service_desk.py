"""Service desk — backend tests."""
import pytest


def test_service_ticket_model_importable():
    from app.models.service_ticket import ServiceTicket
    assert ServiceTicket.__tablename__ == "service_tickets"
