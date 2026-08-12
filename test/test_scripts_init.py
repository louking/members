'''
test_scripts_init - test scripts.catch_errors
=========================================================
'''

# pypi
import pytest

# homegrown
from scripts import catch_errors, ParameterError


def test_catch_errors_returns_none_on_success(bareapp):
    @catch_errors
    def fn():
        return 'ignored'

    with bareapp.app_context():
        assert fn() is None


def test_catch_errors_exits_on_parameter_error(bareapp, capsys):
    @catch_errors
    def fn():
        raise ParameterError('bad input')

    with bareapp.app_context():
        with pytest.raises(SystemExit) as exc_info:
            fn()
    assert exc_info.value.code == 1
    assert 'bad input' in capsys.readouterr().out


def test_catch_errors_exits_on_runtime_error(bareapp, capsys):
    @catch_errors
    def fn():
        raise RuntimeError('boom')

    with bareapp.app_context():
        with pytest.raises(SystemExit) as exc_info:
            fn()
    assert exc_info.value.code == 1
    assert 'boom' in capsys.readouterr().out


def test_catch_errors_lets_other_exceptions_propagate(bareapp):
    @catch_errors
    def fn():
        raise ValueError('unexpected')

    with bareapp.app_context():
        with pytest.raises(ValueError):
            fn()
