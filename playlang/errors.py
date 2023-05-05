# Copyright (C) 2023 pom@vro.life
# SPDX-License-Identifier: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only

class ConflictError(Exception):
    pass


class ConflictShiftReduceError(ConflictError):
    pass


class ConflictReduceReduceError(ConflictError):
    pass
