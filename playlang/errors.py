

class MismatchError(Exception):
    pass


class ConflictError(Exception):
    pass


class ConflictShiftReduceError(ConflictError):
    pass


class ConflictReduceReduceError(ConflictError):
    pass
