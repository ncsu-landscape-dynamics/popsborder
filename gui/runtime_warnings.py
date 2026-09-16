# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

import logging
import warnings


_USE_CONTAINER_WIDTH_WARNING = "Please replace `use_container_width` with `width`"


class _SuppressUseContainerWidthFilter(logging.Filter):
    """Filter that suppresses specific Streamlit deprecation warnings."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Determine whether a log record should be emitted.

        This filter returns False for log messages containing the
        ``_USE_CONTAINER_WIDTH_WARNING`` string, effectively hiding those
        records, and True for all others.

        Args:
            record: Log record to inspect.

        Returns:
            True if the record should be emitted, False otherwise.
        """
        return _USE_CONTAINER_WIDTH_WARNING not in record.getMessage()


def _patch_streamlit_deprecation_warning() -> None:
    """Patch Streamlit's deprecation warning function to filter one message.

    If available, this wraps ``streamlit.deprecation_util.show_deprecation_warning``
    to ignore messages that contain the ``_USE_CONTAINER_WIDTH_WARNING`` text.
    Other deprecation warnings are passed through unchanged.
    """
    try:
        import streamlit.deprecation_util as deprecation_util
    except Exception:
        return

    original = getattr(deprecation_util, "show_deprecation_warning", None)
    if original is None or getattr(original, "_popsborder_filtered", False):
        return

    def _filtered_show_deprecation_warning(message: str) -> None:
        if _USE_CONTAINER_WIDTH_WARNING in message:
            return
        original(message)

    _filtered_show_deprecation_warning._popsborder_filtered = True  # type: ignore[attr-defined]
    deprecation_util.show_deprecation_warning = _filtered_show_deprecation_warning


def suppress_optional_dependency_warnings() -> None:
    """Suppress known optional-dependency and layout warnings in the app.

    This helper:

    * Ignores specific pandas optional-dependency warnings (numexpr, bottleneck).
    * Ignores the known Streamlit ``use_container_width`` deprecation warning.
    * Installs a logging filter on Streamlit's deprecation logger to block
      matching messages.
    * Patches Streamlit's deprecation warning function to avoid emitting the
      ``use_container_width`` warning.

    It is intended to be called early in the application startup.
    """
    warnings.filterwarnings(
        "ignore",
        message=r"Pandas requires version '2\.8\.4' or newer of 'numexpr'.*",
        category=UserWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r"Pandas requires version '1\.3\.6' or newer of 'bottleneck'.*",
        category=UserWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r"Please replace `use_container_width` with `width`.*",
        category=Warning,
    )

    streamlit_deprecation_logger = logging.getLogger("streamlit.deprecation_util")
    if not any(
        isinstance(existing_filter, _SuppressUseContainerWidthFilter)
        for existing_filter in streamlit_deprecation_logger.filters
    ):
        streamlit_deprecation_logger.addFilter(_SuppressUseContainerWidthFilter())
    for handler in streamlit_deprecation_logger.handlers:
        if not any(
            isinstance(existing_filter, _SuppressUseContainerWidthFilter)
            for existing_filter in handler.filters
        ):
            handler.addFilter(_SuppressUseContainerWidthFilter())

    _patch_streamlit_deprecation_warning()
