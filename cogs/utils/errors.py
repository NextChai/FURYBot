
__all__ = (
    'FuryException',
    'ProfanityFailure'
)

class FuryException(Exception):
    pass

class ProfanityFailure(FuryException):
    pass