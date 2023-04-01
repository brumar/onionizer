import nox

# An example nox task definition that runs on many supported Python versions:
@nox.session(python=["3.7", "3.8", "3.9"])
def test(session):
    session.run("pytest")
