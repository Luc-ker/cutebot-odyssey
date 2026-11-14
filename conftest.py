def pytest_configure(config):
    config.addinivalue_line("markers", "slow: needs a real model or hardware; deselect with -m 'not slow'")
