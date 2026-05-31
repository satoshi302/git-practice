class KindleRecoveryError(Exception):
    pass


class DeviceNotFoundError(KindleRecoveryError):
    pass


class SDPError(KindleRecoveryError):
    pass


class UARTError(KindleRecoveryError):
    pass


class UBootError(KindleRecoveryError):
    pass


class FlashError(KindleRecoveryError):
    pass


class HABSecurityError(SDPError):
    """Device has HAB fuses blown; only signed images accepted."""
    pass
