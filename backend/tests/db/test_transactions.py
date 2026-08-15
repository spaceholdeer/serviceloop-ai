from unittest.mock import MagicMock

import pytest

from app.db.session import transactional_session


def test_transaction_commits_and_closes_after_success():
    session = MagicMock()
    factory = MagicMock(return_value=session)

    with transactional_session(factory) as active_session:
        assert active_session is session

    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()
    session.close.assert_called_once_with()


def test_transaction_rolls_back_and_closes_after_error():
    session = MagicMock()
    factory = MagicMock(return_value=session)

    with pytest.raises(RuntimeError, match="write failed"), transactional_session(factory):
        raise RuntimeError("write failed")

    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()
