"""Exceptions for the Sesame BLE integration."""


class SesameBleError(Exception):
    """Base integration error."""


class InvalidCredentialsError(SesameBleError):
    """Raised when a share URL or secret key is invalid."""


class DeviceMismatchError(SesameBleError):
    """Raised when credentials belong to another Sesame device."""


class UnsupportedDeviceError(SesameBleError):
    """Raised when the discovered or shared Sesame model is unsupported."""
