import nox


# An example nox task definition that runs on many supported Python versions:
@nox.session(python=["3.7", "3.8", "3.9", "3.10"])
def test(session):
    session.run("pytest", "--cov=onionizer", "--cov-report=html")
    session.run("mutmut", "run")
