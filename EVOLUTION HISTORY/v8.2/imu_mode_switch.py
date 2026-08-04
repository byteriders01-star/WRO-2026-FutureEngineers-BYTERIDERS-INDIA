from enum import Enum


class ImuCorrectionMode(Enum):
    """Available IMU correction modes."""

    FULL = "full"
    YAW_ONLY = "yaw_only"
    GYRO_ONLY = "gyro_only"


class ImuModeController:
    """Controls the correction mode of a Mahony IMU filter."""

    def __init__(self) -> None:
        self._mode = ImuCorrectionMode.FULL

    def set_mode(self, mode: ImuCorrectionMode) -> None:
        if not isinstance(mode, ImuCorrectionMode):
            raise TypeError("mode must be an ImuCorrectionMode")
        self._mode = mode

    def get_mode(self) -> ImuCorrectionMode:
        return self._mode

    def apply_to_filter(self, mahony_filter) -> None:
        """
        Apply the selected correction mode to a Mahony filter.

        The filter object is expected to have 'kp' and 'ki' attributes.
        """

        if self._mode in (
            ImuCorrectionMode.FULL,
            ImuCorrectionMode.YAW_ONLY,
        ):
            mahony_filter.kp = 2.0
            mahony_filter.ki = 0.1

        elif self._mode == ImuCorrectionMode.GYRO_ONLY:
            mahony_filter.kp = 0.0
            mahony_filter.ki = 0.0

        else:
            raise ValueError(f"Unsupported IMU correction mode: {self._mode}")