class DomainValidationError(ValueError):
    pass


class InvalidIPAddressError(DomainValidationError):
    pass


class InvalidPortError(DomainValidationError):
    pass


class InvalidTimestampError(DomainValidationError):
    pass


class InvalidFlowMetricError(DomainValidationError):
    pass
